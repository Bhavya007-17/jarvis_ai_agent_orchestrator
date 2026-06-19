#!/usr/bin/env python
"""Jarvis multi-model planning council (Phase 4) — planning only.

Pipeline (superpowers methodology: propose -> critique -> synthesize):
  1. propose x3   — three DISTINCT NIM model families (NIM_COUNCIL_1/2/3),
                    each given a different lens, propose an approach.
  2. critique x1  — the reasoning model (NIM_MODEL_REASONING) deliberates over
                    all three proposals with enable_thinking=true.
  3. synthesize x1 — the reasoning model merges proposals + critique into a
                    single plan (enable_thinking=true). HOW it merges is the
                    `synthesis_directive` policy seam (tune to taste).
  4. execute x1   — a SINGLE model (NIM_MODEL_GENERAL) acts on the plan.

Hard rules honored:
  - Every LLM call rides OpenJarvis's LiteLLMEngine via the Phase-1
    `complete_with_fallback` ladder => exponential backoff + NIM->Gemini->local
    fallback, so the council never melts the free NIM tier (no 429 storm).
  - No hardcoded model IDs — every model string comes from .env.
  - enable_thinking (reasoning mode) is ON only for critic + synthesizer.
  - The deliberation is represented as an a2a `A2ATask` (state + history).

Usage:
    uv run python scripts/jarvis_council.py "how should I add rate limiting to the API?"
    uv run python scripts/jarvis_council.py --no-stream "design a caching layer"
    uv run python scripts/jarvis_council.py --no-execute "plan a migration to async"
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # sibling-script imports

# Windows consoles default to cp1252; reasoning models emit non-ASCII. Mirror
# the PYTHONUTF8 fix from Phase 2 so a direct `python ...` run never crashes.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:  # noqa: BLE001 - older/odd streams; best effort
    pass

from jarvis_router import (  # noqa: E402
    NIM_PROVIDER,
    complete_with_fallback,
)
from openjarvis.a2a.protocol import A2ATask, TaskState  # noqa: E402
from openjarvis.core.types import Message, Role  # noqa: E402
from openjarvis.engine.litellm import LiteLLMEngine  # noqa: E402

# Reasoning models (DeepSeek/Nemotron/Kimi) take a non-standard switch; LiteLLM
# forwards extra_body untouched (engine litellm.py:63). ON = deliberate.
THINKING_ON = {"chat_template_kwargs": {"enable_thinking": True}}

# Three distinct lenses so three model families produce genuinely different
# proposals instead of three rewrites of the same idea. Diversity is the whole
# point of a council.
COUNCIL_PERSONAS: tuple[tuple[str, str], ...] = (
    (
        "Pragmatist",
        "You favor the simplest thing that works. Optimize for shipping fast "
        "with the least risk and moving parts. Call out what to NOT build.",
    ),
    (
        "Architect",
        "You favor long-term structure: clean boundaries, scalability, and "
        "maintainability. Think about how this evolves over the next year.",
    ),
    (
        "Skeptic",
        "You hunt failure modes. Surface edge cases, race conditions, security "
        "and cost risks, and the ways a naive approach breaks in production.",
    ),
)


# ---------------------------------------------------------------------------
# Model selection (all ids from .env, never hardcoded)
# ---------------------------------------------------------------------------


def council_models() -> list[str]:
    """The (up to 3) DISTINCT council model ids from .env, in order."""
    ids = [
        os.environ.get(f"NIM_COUNCIL_{i}", "").strip() for i in (1, 2, 3)
    ]
    seen: list[str] = []
    for mid in ids:
        if mid and mid not in seen:
            seen.append(mid)
    return seen


def _reasoning_model() -> str:
    return os.environ.get("NIM_MODEL_REASONING", "").strip()


def _general_model() -> str:
    return os.environ.get("NIM_MODEL_GENERAL", "").strip()


def _ladder_from(primary_full: str, *, also: list[str] | None = None) -> list[tuple[str, str]]:
    """Build a [(label, full_model_id)] ladder with ``primary_full`` first.

    The cross-vendor tail (Gemini -> local Ollama) is identical to the router's
    so the council inherits the same 429/timeout protection.
    """
    gemini = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini/gemini-2.0-flash").strip()
    local = os.environ.get("LOCAL_FALLBACK_MODEL", "ollama/qwen2.5:7b").strip()
    ladder: list[tuple[str, str]] = [("NIM-A", primary_full)]
    for i, extra in enumerate(also or [], start=1):
        if extra and extra != primary_full:
            ladder.append((f"NIM-{chr(ord('B') + i - 1)}", extra))
    if gemini:
        ladder.append(("Gemini", gemini))
    if local:
        ladder.append(("local", local))
    return ladder


def _nim(model_id: str) -> str:
    """Prefix a bare NIM model id with the LiteLLM provider route."""
    return f"{NIM_PROVIDER}/{model_id}"


# ---------------------------------------------------------------------------
# One council "voice" — stream the primary rung, fall back to the ladder.
# ---------------------------------------------------------------------------


async def _astream(engine: LiteLLMEngine, messages: list[Message], model: str,
                   max_tokens: int, extra_body: dict | None,
                   emit=None, label: str = "") -> str:
    kwargs: dict = {"max_tokens": max_tokens}
    if extra_body:
        kwargs["extra_body"] = extra_body
    parts: list[str] = []
    async for piece in engine.stream(messages, model=model, **kwargs):
        parts.append(piece)
        print(piece, end="", flush=True)
        if emit:
            emit({"type": "voice_chunk", "label": label, "content": piece})
    return "".join(parts)


def voice(label: str, messages: list[Message], ladder: list[tuple[str, str]], *,
          max_tokens: int, extra_body: dict | None = None, stream: bool = True,
          emit=None) -> dict:
    """Run one voice. Stream the primary rung live; on any failure walk the
    laddered, backed-off `complete_with_fallback`. Returns its result dict.
    """
    print(f"\n{'=' * 70}\n[{label}]  primary={ladder[0][1]}\n{'-' * 70}")
    if emit:
        emit({"type": "voice_start", "label": label, "model": ladder[0][1]})
    if stream:
        try:
            text = asyncio.run(
                _astream(LiteLLMEngine(), messages, ladder[0][1], max_tokens,
                         extra_body, emit=emit, label=label)
            )
            if text.strip():
                print()
                if emit:
                    emit({"type": "voice_end", "label": label, "content": text,
                          "model": ladder[0][1], "rung": ladder[0][0]})
                return {"content": text, "model": ladder[0][1],
                        "rung": ladder[0][0], "path": [f"{ladder[0][0]}:stream-ok"]}
            print("[empty stream; using laddered call]", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 - any stream error => ladder
            print(f"\n[stream failed: {type(exc).__name__}; using laddered call]",
                  file=sys.stderr)

    result = complete_with_fallback(
        messages, "general", max_tokens=max_tokens,
        extra_body=extra_body, ladder=ladder,
    )
    print(result["content"])
    if emit:
        emit({"type": "voice_chunk", "label": label, "content": result["content"]})
        emit({"type": "voice_end", "label": label, "content": result["content"],
              "model": result["model"], "rung": result["rung"]})
    return result


# ---------------------------------------------------------------------------
# Synthesis policy — THE tunable seam (mirrors Phase 3's `decide_fact`).
# ---------------------------------------------------------------------------


def synthesis_directive(proposals: list[dict], critique: str) -> str:
    """Decide HOW the synthesizer should merge the council's output.

    This is the meaningful design choice of the whole feature: given three
    proposals (each a {"persona","content"} dict) and the critic's analysis,
    what instruction governs the final plan? The synthesizer obeys whatever
    string this returns. Trade-offs to weigh:

      - "merge-strengths": combine the best ideas from all three. Richest plan,
        but risks an incoherent grab-bag if the proposals disagree.
      - "winner-take-all": adopt the single strongest proposal, discard the
        rest. Most coherent, but throws away minority insight.
      - "critic-weighted": let the critique drive — prioritize whatever the
        critic flagged as essential, demote what it called risky.

    Default below = critic-weighted merge. Tune the policy to taste: e.g. read
    the critique for a "winner", or count how many proposals agree on a step.
    """
    return (
        "Merge the proposals into ONE coherent plan, led by the critique: "
        "adopt every idea the critique calls essential, drop or guard anything "
        "it flags as risky, and resolve disagreements in favor of the safer, "
        "more concrete option. Prefer a small number of well-justified steps "
        "over a grab-bag of everything proposed."
    )


# ---------------------------------------------------------------------------
# The council
# ---------------------------------------------------------------------------


def run_council(task: str, *, stream: bool = True, execute: bool = True,
                max_tokens: int = 500, emit=None) -> A2ATask:
    voices = council_models()
    if len(voices) < 2:
        raise RuntimeError(
            "Need >=2 distinct NIM_COUNCIL_* model ids in .env for a council; "
            f"found {voices}"
        )
    reasoning = _reasoning_model()
    if not reasoning:
        raise RuntimeError("NIM_MODEL_REASONING is unset in .env (critic/synth).")

    a2a = A2ATask(input_text=task, state=TaskState.WORKING)
    a2a.metadata["voices"] = voices

    # --- 1. propose x3 (or xN distinct) -----------------------------------
    proposals: list[dict] = []
    for idx, model_id in enumerate(voices[:3]):
        persona, lens = COUNCIL_PERSONAS[idx % len(COUNCIL_PERSONAS)]
        msgs = [
            Message(role=Role.SYSTEM, content=(
                f"You are the {persona} on a planning council. {lens} "
                "Propose a concrete approach to the user's task as a short "
                "numbered plan (4-7 steps). Be specific; no preamble.")),
            Message(role=Role.USER, content=task),
        ]
        # proposer ladder: this council model, then the OTHER council models,
        # then cross-vendor. enable_thinking stays OFF for clean proposals.
        ladder = _ladder_from(_nim(model_id),
                              also=[_nim(m) for m in voices if m != model_id])
        res = voice(f"PROPOSAL {idx + 1} — {persona}", msgs, ladder,
                    max_tokens=max_tokens, stream=stream, emit=emit)
        proposals.append({"persona": persona, "content": res["content"],
                          "served_by": res["model"]})
        a2a.history.append({"role": f"proposer:{persona}", "content": res["content"]})

    # --- 2. critique x1 (reasoning, thinking ON) --------------------------
    bundle = "\n\n".join(
        f"### Proposal {i + 1} ({p['persona']})\n{p['content']}"
        for i, p in enumerate(proposals)
    )
    crit_msgs = [
        Message(role=Role.SYSTEM, content=(
            "You are the council critic. Compare the proposals below. Identify "
            "the strongest ideas, contradictions, missing risks, and which "
            "approach is safest. Be decisive and concise.")),
        Message(role=Role.USER, content=f"Task: {task}\n\n{bundle}"),
    ]
    crit_ladder = _ladder_from(_nim(reasoning), also=[_nim(voices[0])])
    crit = voice("CRITIQUE — reasoning", crit_msgs, crit_ladder,
                 max_tokens=max_tokens, extra_body=THINKING_ON, stream=stream, emit=emit)
    a2a.history.append({"role": "critic", "content": crit["content"]})

    # --- 3. synthesize x1 (reasoning, thinking ON, policy seam) -----------
    directive = synthesis_directive(proposals, crit["content"])
    synth_msgs = [
        Message(role=Role.SYSTEM, content=(
            "You are the council synthesizer. Produce ONE final implementation "
            "plan as a numbered list of bite-sized steps, each naming concrete "
            f"actions. {directive}")),
        Message(role=Role.USER, content=(
            f"Task: {task}\n\n{bundle}\n\n### Critique\n{crit['content']}")),
    ]
    synth_ladder = _ladder_from(_nim(reasoning), also=[_nim(voices[0])])
    synth = voice("SYNTHESIZED PLAN — reasoning", synth_msgs, synth_ladder,
                  max_tokens=max_tokens + 200, extra_body=THINKING_ON, stream=stream, emit=emit)
    a2a.output_text = synth["content"]
    a2a.history.append({"role": "synthesizer", "content": synth["content"]})

    # --- 4. execute x1 (single model, thinking OFF) -----------------------
    if execute:
        gen = _general_model()
        exec_msgs = [
            Message(role=Role.SYSTEM, content=(
                "You are the single executor agent. Take the plan below and "
                "carry out STEP 1 only: do the work or produce the first "
                "concrete artifact (code/command/text). Note what remains.")),
            Message(role=Role.USER, content=synth["content"]),
        ]
        exec_ladder = _ladder_from(_nim(gen) if gen else _nim(voices[0]))
        ex = voice("EXECUTOR — single model", exec_msgs, exec_ladder,
                   max_tokens=max_tokens, stream=stream, emit=emit)
        a2a.metadata["executor_model"] = ex["model"]
        a2a.history.append({"role": "executor", "content": ex["content"]})

    if emit:
        emit({"type": "council_done", "voices": voices,
              "executor": a2a.metadata.get("executor_model")})
    a2a.state = TaskState.COMPLETED
    return a2a


def main() -> int:
    parser = argparse.ArgumentParser(description="Jarvis multi-model planning council")
    parser.add_argument("task", nargs="+", help="the planning task / question")
    parser.add_argument("--no-stream", action="store_true",
                        help="disable token streaming (laddered calls only)")
    parser.add_argument("--no-execute", action="store_true",
                        help="stop after the synthesized plan (planning only)")
    parser.add_argument("--max-tokens", type=int, default=500)
    args = parser.parse_args()

    try:
        a2a = run_council(
            " ".join(args.task),
            stream=not args.no_stream,
            execute=not args.no_execute,
            max_tokens=args.max_tokens,
        )
    except RuntimeError as exc:
        print(f"\n[council FAILED] {exc}", file=sys.stderr)
        return 1

    print(f"\n{'=' * 70}\n[council {a2a.state.value}] task={a2a.task_id}")
    print(f"  voices    : {', '.join(a2a.metadata.get('voices', []))}")
    print(f"  turns     : {len(a2a.history)} "
          f"({sum(1 for h in a2a.history if h['role'].startswith('proposer'))} proposals, "
          "1 critique, 1 plan"
          + (", 1 execution" if 'executor_model' in a2a.metadata else "") + ")")
    if "executor_model" in a2a.metadata:
        print(f"  executor  : {a2a.metadata['executor_model']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
