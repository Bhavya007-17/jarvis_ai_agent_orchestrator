#!/usr/bin/env python
"""Jarvis router + multi-model fallback ladder + doctor (Phase 1).

- Routes a task to the right NIM model by type (reasoning / code / general),
  pulling the model IDs from .env (never hardcoded).
- Calls it through the fallback ladder NIM-A -> NIM-B -> Gemini Flash -> local
  Ollama, with exponential backoff (1s, 2s, 4s; max 3 tries) per rung before
  walking to the next provider. Every LLM call goes through OpenJarvis's
  LiteLLMEngine (src/openjarvis/engine/litellm.py), per the hard rules.
- `doctor` pings each provider, reports up/down, and prints the per-task model
  mapping.

Usage:
    uv run python scripts/jarvis_router.py route "write a python function ..."
    uv run python scripts/jarvis_router.py route --simulate-nim-down "plan an approach to ..."
    uv run python scripts/jarvis_router.py doctor
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import httpx

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(override=False)

# LiteLLM's native nvidia_nim/ provider authenticates with NVIDIA_NIM_API_KEY;
# the spec stores the key as NVIDIA_API_KEY, so mirror it (only if non-empty).
if os.environ.get("NVIDIA_API_KEY") and not os.environ.get("NVIDIA_NIM_API_KEY"):
    os.environ["NVIDIA_NIM_API_KEY"] = os.environ["NVIDIA_API_KEY"]

from openjarvis.core.types import Message, Role  # noqa: E402
from openjarvis.engine.litellm import LiteLLMEngine  # noqa: E402

NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
NIM_PROVIDER = "nvidia_nim"
MAX_TRIES_PER_RUNG = 3

# Keyword heuristics for task-type routing. Order matters: code wins over
# reasoning when both appear (a "plan the code" request is still code work).
_CODE_HINTS = (
    "code", "function", "python", "javascript", "typescript", "java ", "c++",
    "bug", "debug", "implement", "refactor", "regex", "sql", "compile",
    "script", "class ", "method", "api endpoint", "unit test", "stack trace",
)
_REASONING_HINTS = (
    "plan", "approach", "strategy", "architecture", "design ", "trade-off",
    "tradeoff", "step by step", "reason", "analyze", "analyse", "decide",
    "compare", "evaluate", "pros and cons", "think through", "roadmap",
)


def classify(task: str) -> str:
    """Return 'code', 'reasoning', or 'general' for a task string."""
    t = task.lower()
    if any(h in t for h in _CODE_HINTS):
        return "code"
    if any(h in t for h in _REASONING_HINTS):
        return "reasoning"
    return "general"


def _env_model(task_type: str) -> str:
    """Bare NIM model id for a task type, from .env."""
    mapping = {
        "code": "NIM_MODEL_CODE",
        "reasoning": "NIM_MODEL_REASONING",
        "general": "NIM_MODEL_GENERAL",
    }
    return os.environ.get(mapping[task_type], "").strip()


def task_model_map() -> dict[str, str]:
    """Per-task-type -> NIM model id (for doctor / logging)."""
    return {tt: _env_model(tt) for tt in ("reasoning", "code", "general")}


def build_ladder(task_type: str) -> list[tuple[str, str]]:
    """Return the ordered [(label, full_model_id)] fallback ladder.

    NIM-A is the role model; NIM-B is a *different* NIM model (dodges per-model
    429s); then Gemini Flash; then local Ollama. Model strings carry their
    LiteLLM provider prefix so the engine routes correctly.
    """
    primary = _env_model(task_type)
    general = os.environ.get("NIM_MODEL_GENERAL", "").strip()
    reasoning = os.environ.get("NIM_MODEL_REASONING", "").strip()
    secondary = general if general and general != primary else reasoning
    gemini = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini/gemini-2.0-flash").strip()
    local = os.environ.get("LOCAL_FALLBACK_MODEL", "ollama/qwen2.5:7b").strip()

    ladder: list[tuple[str, str]] = []
    if primary:
        ladder.append(("NIM-A", f"{NIM_PROVIDER}/{primary}"))
    if secondary and secondary != primary:
        ladder.append(("NIM-B", f"{NIM_PROVIDER}/{secondary}"))
    if gemini:
        ladder.append(("Gemini", gemini))
    if local:
        ladder.append(("local", local))
    return ladder


def _rung_has_key(label: str) -> bool:
    """True if the provider for this rung has a usable key (local always ok)."""
    if label.startswith("NIM"):
        return bool(os.environ.get("NVIDIA_NIM_API_KEY", "").strip())
    if label == "Gemini":
        return bool(os.environ.get("GEMINI_API_KEY", "").strip())
    return True  # local Ollama needs no key


def _is_retryable(exc: Exception) -> bool:
    """Backoff+retry on rate-limit / timeout / transient 5xx; else move on."""
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    retry_markers = (
        "ratelimit", "timeout", "serviceunavailable", "internalservererror",
        "apiconnection", "overloaded", " 429", " 500", " 502", " 503",
    )
    if any(m in name for m in ("ratelimit", "timeout", "serviceunavailable",
                               "apiconnection", "internalservererror")):
        return True
    return any(m in msg for m in retry_markers)


def complete_with_fallback(
    messages: list[Message],
    task_type: str,
    *,
    max_tokens: int = 256,
    skip_nim: bool = False,
    extra_body: dict | None = None,
    ladder: list[tuple[str, str]] | None = None,
) -> dict:
    """Walk the fallback ladder; return a result dict with the path taken.

    Returns {content, model, rung, path} on success, raising RuntimeError only
    if every rung fails (no silent empty result).

    If ``ladder`` is given it is used verbatim (the council passes a
    specific-model-first ladder); otherwise it is built from ``task_type``.
    Either way the same retry/backoff loop runs, so callers inherit the
    Phase-1 429 protection for free.
    """
    engine = LiteLLMEngine()
    if ladder is None:
        ladder = build_ladder(task_type)
    path: list[str] = []
    kwargs: dict = {"max_tokens": max_tokens}
    if extra_body:
        kwargs["extra_body"] = extra_body

    for label, model in ladder:
        if skip_nim and label.startswith("NIM"):
            path.append(f"{label}:skipped(simulated-down)")
            continue
        if not _rung_has_key(label):
            path.append(f"{label}:skipped(no-key)")
            continue

        for attempt in range(1, MAX_TRIES_PER_RUNG + 1):
            try:
                print(f"  -> trying {label} ({model}) attempt {attempt}", file=sys.stderr)
                result = engine.generate(messages, model=model, **kwargs)
                path.append(f"{label}:ok")
                result["rung"] = label
                result["path"] = path
                return result
            except Exception as exc:  # noqa: BLE001 - we classify below
                if _is_retryable(exc) and attempt < MAX_TRIES_PER_RUNG:
                    backoff = 2 ** (attempt - 1)  # 1s, 2s, 4s
                    print(f"     retryable error ({type(exc).__name__}); "
                          f"backing off {backoff}s", file=sys.stderr)
                    time.sleep(backoff)
                    continue
                path.append(f"{label}:fail({type(exc).__name__})")
                break  # non-retryable or out of tries -> next rung

    raise RuntimeError(f"All fallback rungs failed. Path: {' -> '.join(path)}")


# ---------------------------------------------------------------------------
# CLI subcommands
# ---------------------------------------------------------------------------


def cmd_route(args: argparse.Namespace) -> int:
    task = " ".join(args.task)
    task_type = classify(task)
    ladder = build_ladder(task_type)
    print(f"[route] task_type = {task_type}")
    print(f"[route] chosen model = {ladder[0][1] if ladder else '(none)'}")
    print(f"[route] ladder = {[l for l, _ in ladder]}")

    messages = [
        Message(role=Role.SYSTEM, content="You are Jarvis. Be concise."),
        Message(role=Role.USER, content=task),
    ]
    try:
        result = complete_with_fallback(
            messages, task_type, max_tokens=args.max_tokens,
            skip_nim=args.simulate_nim_down,
        )
    except RuntimeError as exc:
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        return 1
    print(f"\n[served-by] rung={result['rung']} model={result['model']}")
    print(f"[path] {' -> '.join(result['path'])}")
    print(f"\n{result['content']}")
    return 0


def _probe_nim() -> str:
    key = os.environ.get("NVIDIA_NIM_API_KEY", "").strip()
    if not key:
        return "NO KEY"
    try:
        r = httpx.get(f"{NIM_BASE_URL}/models",
                      headers={"Authorization": f"Bearer {key}"}, timeout=15)
        return f"UP ({len(r.json().get('data', []))} models)" if r.status_code == 200 \
            else f"DOWN (HTTP {r.status_code})"
    except httpx.HTTPError as exc:
        return f"DOWN ({type(exc).__name__})"


def _probe_gemini() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return "NO KEY"
    try:
        r = httpx.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
            timeout=15,
        )
        return "UP" if r.status_code == 200 else f"DOWN (HTTP {r.status_code})"
    except httpx.HTTPError as exc:
        return f"DOWN ({type(exc).__name__})"


def _probe_ollama() -> str:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    try:
        r = httpx.get(f"{host}/api/tags", timeout=10)
        names = [m["name"] for m in r.json().get("models", [])]
        return f"UP ({len(names)} models)" if r.status_code == 200 else "DOWN"
    except httpx.HTTPError as exc:
        return f"DOWN ({type(exc).__name__})"


def cmd_doctor(_args: argparse.Namespace) -> int:
    print("Jarvis doctor — provider health\n")
    print(f"  NIM    : {_probe_nim()}")
    print(f"  Gemini : {_probe_gemini()}")
    print(f"  Ollama : {_probe_ollama()}")
    print("\nPer-task model mapping (from .env):")
    for tt, model in task_model_map().items():
        print(f"  {tt:<10} -> {NIM_PROVIDER}/{model}" if model
              else f"  {tt:<10} -> (unset)")
    print("\nFallback ladder (example, reasoning task):")
    print("  " + " -> ".join(f"{l}({m})" for l, m in build_ladder("reasoning")))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Jarvis router + fallback + doctor")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_route = sub.add_parser("route", help="route a task and answer with fallback")
    p_route.add_argument("task", nargs="+", help="the task / question")
    p_route.add_argument("--max-tokens", type=int, default=256)
    p_route.add_argument("--simulate-nim-down", action="store_true",
                         help="skip NIM rungs to exercise the fallback ladder")
    p_route.set_defaults(func=cmd_route)

    p_doctor = sub.add_parser("doctor", help="provider health + per-task mapping")
    p_doctor.set_defaults(func=cmd_doctor)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
