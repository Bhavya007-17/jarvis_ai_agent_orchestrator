#!/usr/bin/env python
"""Phase 3 follow-up — LLM-driven auto-extraction of personal facts.

Mark-XL captures facts by having the model call a ``save_memory`` tool mid-turn
(see `_vendor/Mark-XL/main.py` + `core/prompt.txt`). This module ports the same
*idea* as a post-hoc pipeline so the capture policy is explicit and tunable:

    conversation text
      -> LLM extraction       (via OpenJarvis LiteLLMEngine + the Phase-1
                               fallback ladder — `jarvis_router.complete_with_fallback`,
                               honoring the hard rule that every LLM call goes
                               through the engine, never raw)
      -> candidate facts      (JSON: category/key/value/confidence)
      -> decide_fact(...)     <-- THE POLICY SEAM (you own this)
      -> FactsStore.remember  (-> personal_facts.json -> USER.md injection)

Everything around the policy is built and tested; only ``decide_fact`` is a
deliberately thin seam where the judgment lives — what to capture, when to
overwrite vs. keep, and the confidence bar. A conservative default is provided
so the pipeline runs today; tune it to taste.

Usage:
    uv run python scripts/jarvis_automem.py "my name is Bhavya and I prefer Python"
    uv run python scripts/jarvis_automem.py --dry-run "I live in Blacksburg"
    echo "I'm working on the Jarvis orchestrator" | uv run python scripts/jarvis_automem.py -
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # sibling-script imports

from jarvis_memory import VALID_CATEGORIES, FactsStore  # noqa: E402
from jarvis_router import complete_with_fallback  # noqa: E402
from openjarvis.core.types import Message, Role  # noqa: E402

# ---------------------------------------------------------------------------
# Tuning knobs — surfaced as constants so the policy reads cleanly.
# ---------------------------------------------------------------------------
#: Candidates below this model-reported confidence are dropped outright.
MIN_CONFIDENCE = 0.6

_EXTRACTION_SYSTEM = (
    "You extract DURABLE personal facts about the user from a message. "
    "Return ONLY a JSON array (no prose, no code fences). Each item: "
    '{"category": one of '
    f"{list(VALID_CATEGORIES)}, "
    '"key": short snake_case identifier, "value": concise fact, '
    '"confidence": 0.0-1.0}. '
    "Capture only lasting facts (name, age, city, job, preferences, projects, "
    "relationships, goals) — NOT transient chit-chat, questions, or tasks. "
    "If there is nothing durable, return []."
)


@dataclass(slots=True)
class Candidate:
    """A fact the model proposes storing."""

    category: str
    key: str
    value: str
    confidence: float


# ---------------------------------------------------------------------------
# Extraction (LLM) — fully implemented, routed through the engine + ladder.
# ---------------------------------------------------------------------------
def _parse_candidates(raw: str) -> list[Candidate]:
    """Best-effort parse of the model's JSON array (tolerant of fences/prose)."""
    text = raw.strip()
    if "```" in text:  # strip ```json ... ``` fences if the model adds them
        text = text.split("```")[1].lstrip("json").strip() if text.count("```") >= 2 else text
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        items = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    out: list[Candidate] = []
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        cat = str(it.get("category", "notes"))
        out.append(
            Candidate(
                category=cat if cat in VALID_CATEGORIES else "notes",
                key=str(it.get("key", "")).strip(),
                value=str(it.get("value", "")).strip(),
                confidence=float(it.get("confidence", 0.0) or 0.0),
            )
        )
    return out


def extract_candidates(text: str) -> list[Candidate]:
    """Ask the model for durable facts in *text*; return parsed candidates."""
    if not text.strip():
        return []
    messages = [
        Message(role=Role.SYSTEM, content=_EXTRACTION_SYSTEM),
        Message(role=Role.USER, content=text),
    ]
    # "general" task type -> NIM general model, with Gemini/local fallback.
    result = complete_with_fallback(messages, "general", max_tokens=400)
    return _parse_candidates(result.get("content", ""))


# ---------------------------------------------------------------------------
# THE POLICY SEAM — this is the ~10 lines worth shaping by hand.
# ---------------------------------------------------------------------------
def decide_fact(candidate: Candidate, existing_value: str | None) -> bool:
    """Decide whether to store *candidate*. Return True to store, False to skip.

    This is the judgment layer of auto-memory. ``existing_value`` is whatever is
    already stored under the same category/key (or ``None`` if nothing is).

    TODO(you): tune this policy. Things worth deciding here —
      * Confidence bar: is MIN_CONFIDENCE the right floor per category?
        (e.g. demand higher confidence for `identity` than `notes`.)
      * Overwrite vs. keep: when a fact already exists and differs, do you
        trust the newer extraction, prefer the longer/more-specific value, or
        never silently overwrite identity facts?
      * Key hygiene: reject empty/garbage keys, cap value length, dedupe
        near-duplicates.
    The default below is intentionally conservative: store only confident
    candidates, and overwrite an existing value only when it actually changed.
    """
    if candidate.confidence < MIN_CONFIDENCE:
        return False
    if not candidate.key or not candidate.value:
        return False
    if existing_value is not None and existing_value == candidate.value:
        return False  # already known, no change
    return True


# ---------------------------------------------------------------------------
# Orchestration — extract -> decide -> store.
# ---------------------------------------------------------------------------
def auto_extract(text: str, store: FactsStore | None = None, *, dry_run: bool = False) -> list[str]:
    """Run the full pipeline; return human-readable lines for what happened."""
    store = store or FactsStore()
    memory = store.load()
    lines: list[str] = []
    for c in extract_candidates(text):
        existing = memory.get(c.category, {}).get(c.key, {})
        existing_value = existing.get("value") if isinstance(existing, dict) else None
        if not decide_fact(c, existing_value):
            lines.append(f"skip  [{c.confidence:.2f}] {c.category}/{c.key} = {c.value}")
            continue
        if dry_run:
            lines.append(f"WOULD store [{c.confidence:.2f}] {c.category}/{c.key} = {c.value}")
        else:
            lines.append(store.remember(c.key, c.value, c.category))
    return lines or ["No durable facts found."]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Auto-extract personal facts from text.")
    p.add_argument("text", help="Conversation text, or '-' to read stdin.")
    p.add_argument("--dry-run", action="store_true", help="Show decisions, store nothing.")
    args = p.parse_args(argv)
    text = sys.stdin.read() if args.text == "-" else args.text
    for line in auto_extract(text, dry_run=args.dry_run):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
