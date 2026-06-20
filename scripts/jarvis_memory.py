#!/usr/bin/env python
"""Jarvis memory (Phase 3) — three scopes wired onto OpenJarvis, no Rust needed.

PRIME DIRECTIVE compliance — this is a *port + wire*, not a rewrite:

  - personal_facts : Mark-XL's structured-facts logic
      (`_vendor/Mark-XL/memory/memory_manager.py`) ported onto OpenJarvis
      storage paths (`~/.openjarvis/personal_facts.json`) and *rendered into
      OpenJarvis's own `USER.md`*. OpenJarvis's `SystemPromptBuilder`
      (`src/openjarvis/prompt/builder.py`) already injects USER.md as the
      "User Profile" section of every `jarvis ask` system prompt, so a stored
      fact is recalled on every later turn with no extra plumbing.
  - session        : reuses OpenJarvis's pure-Python `SessionStore`
      (`src/openjarvis/sessions/session.py`, sqlite) — read recent turns.
  - code_graph     : already wired in Phase 2 (codebase-memory MCP, :9749).
      This CLI only points at it; the orchestrator answers code questions via
      the MCP tools (`jarvis ask --agent operative`).

Why not the OpenJarvis vector backend (`jarvis memory`)? Its sqlite/bm25
backends hard-require the native `openjarvis_rust` extension, which is not
built in this venv (`RUST_AVAILABLE = False`). Building it (maturin + rustc
>= 1.88) is a heavy global install left as a follow-up; the personal-facts
scope, which is what the Phase 3 gate needs, has no such dependency.

Usage:
    uv run python scripts/jarvis_memory.py remember --category identity name "Bhavya"
    uv run python scripts/jarvis_memory.py remember favorite_language "Python"
    uv run python scripts/jarvis_memory.py forget --category identity name
    uv run python scripts/jarvis_memory.py show
    uv run python scripts/jarvis_memory.py render          # rebuild USER.md
    uv run python scripts/jarvis_memory.py session [--user default] [--limit 10]
    uv run python scripts/jarvis_memory.py code            # how to query the code graph
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from threading import Lock

from openjarvis.core.paths import get_config_dir

# --- ported constants (Mark-XL memory_manager.py) --------------------------
VALID_CATEGORIES = (
    "identity",
    "preferences",
    "projects",
    "relationships",
    "wishes",
    "notes",
)
MAX_VALUE_LENGTH = 380
MEMORY_MAX_CHARS = 2200

# OpenJarvis storage seam: structured facts live next to the rest of the
# OpenJarvis state, and render into the file the prompt builder already reads.
FACTS_PATH = get_config_dir() / "personal_facts.json"
USER_MD_PATH = get_config_dir() / "USER.md"

# Sentinel so the renderer only ever owns its own block inside USER.md and
# never clobbers anything a user (or another phase) hand-wrote there.
_RENDER_BEGIN = "<!-- JARVIS:personal_facts BEGIN (auto-generated) -->"
_RENDER_END = "<!-- JARVIS:personal_facts END -->"

_lock = Lock()


# ---------------------------------------------------------------------------
# FactsStore — Mark-XL's structured-facts logic, ported to OpenJarvis paths.
# ---------------------------------------------------------------------------
class FactsStore:
    """Bounded, deduplicating store of structured personal facts.

    Each fact is ``{"value": str, "updated": "YYYY-MM-DD"}`` filed under a
    category. The store self-trims to ``MEMORY_MAX_CHARS`` by evicting the
    oldest-updated facts first — ported faithfully from Mark-XL.
    """

    def __init__(self, path: Path = FACTS_PATH) -> None:
        self._path = path

    @staticmethod
    def _empty() -> dict:
        return {cat: {} for cat in VALID_CATEGORIES}

    def load(self) -> dict:
        if not self._path.exists():
            return self._empty()
        with _lock:
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                # Never silently swallow: surface, then degrade to empty so a
                # corrupt file can't take down the whole prompt build.
                print(f"[memory] load error ({exc}); starting empty", file=sys.stderr)
                return self._empty()
        if not isinstance(data, dict):
            return self._empty()
        base = self._empty()
        for cat in base:
            if isinstance(data.get(cat), dict):
                base[cat] = data[cat]
        return base

    def _save(self, memory: dict) -> None:
        memory = self._trim_to_limit(memory)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with _lock:
            self._path.write_text(
                json.dumps(memory, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    @staticmethod
    def _truncate(val: str) -> str:
        return val[:MAX_VALUE_LENGTH].rstrip() + "…" if len(val) > MAX_VALUE_LENGTH else val

    def _trim_to_limit(self, memory: dict) -> dict:
        if len(json.dumps(memory, ensure_ascii=False)) <= MEMORY_MAX_CHARS:
            return memory
        entries = [
            (cat, key, entry)
            for cat, items in memory.items()
            if isinstance(items, dict)
            for key, entry in items.items()
            if isinstance(entry, dict) and "value" in entry
        ]
        entries.sort(key=lambda t: t[2].get("updated", "0000-00-00"))
        for cat, key, _ in entries:
            if len(json.dumps(memory, ensure_ascii=False)) <= MEMORY_MAX_CHARS:
                break
            del memory[cat][key]
            print(f"[memory] trimmed {cat}/{key}", file=sys.stderr)
        return memory

    def remember(self, key: str, value: str, category: str = "notes") -> str:
        """Store/refresh one fact. Returns a human-readable confirmation."""
        if category not in VALID_CATEGORIES:
            category = "notes"
        value = value.strip()
        if not key or not value:
            return "Nothing to remember: key and value are both required."
        memory = self.load()
        entry = {"value": self._truncate(value), "updated": datetime.now().strftime("%Y-%m-%d")}
        existing = memory[category].get(key, {})
        if isinstance(existing, dict) and existing.get("value") == entry["value"]:
            return f"Already known: {category}/{key}"
        memory[category][key] = entry
        self._save(memory)
        self.render(memory)
        return f"Remembered: {category}/{key} = {entry['value']}"

    def forget(self, key: str, category: str = "notes") -> str:
        memory = self.load()
        if key in memory.get(category, {}):
            del memory[category][key]
            self._save(memory)
            self.render(memory)
            return f"Forgotten: {category}/{key}"
        return f"Not found: {category}/{key}"

    # -- rendering into OpenJarvis's USER.md (the wired injection seam) ------
    def render(self, memory: dict | None = None) -> Path:
        """Render facts into the auto-managed block of ``USER.md``.

        Preserves any non-Jarvis content already in USER.md; only the block
        between the sentinels is replaced.
        """
        memory = memory if memory is not None else self.load()
        block = f"{_RENDER_BEGIN}\n{format_facts(memory)}\n{_RENDER_END}"
        USER_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing = USER_MD_PATH.read_text(encoding="utf-8") if USER_MD_PATH.exists() else ""
        if _RENDER_BEGIN in existing and _RENDER_END in existing:
            head = existing.split(_RENDER_BEGIN)[0]
            tail = existing.split(_RENDER_END, 1)[1]
            new = f"{head.rstrip()}\n\n{block}\n{tail.lstrip()}".strip() + "\n"
        else:
            new = f"{existing.rstrip()}\n\n{block}\n".lstrip()
        USER_MD_PATH.write_text(new, encoding="utf-8")
        return USER_MD_PATH


def format_facts(memory: dict | None) -> str:
    """Render structured facts as a compact prompt-friendly profile.

    Adapted from Mark-XL's ``format_memory_for_prompt`` — same intent (a
    natural profile, not a recited list), trimmed to OpenJarvis's USER.md
    "User Profile" section.
    """
    if not memory:
        return "(no facts recorded yet)"

    def _val(entry: object) -> str:
        return entry.get("value", "") if isinstance(entry, dict) else str(entry)

    lines: list[str] = []
    headings = {
        "identity": "Identity",
        "preferences": "Preferences",
        "projects": "Active projects / goals",
        "relationships": "People in their life",
        "wishes": "Wishes / plans",
        "notes": "Other notes",
    }
    for cat, heading in headings.items():
        items = memory.get(cat, {})
        rendered = [(k, _val(v)) for k, v in items.items() if _val(v)]
        if not rendered:
            continue
        lines.append(f"**{heading}:**")
        for key, val in rendered:
            lines.append(f"- {key.replace('_', ' ').title()}: {val}")
        lines.append("")

    return "\n".join(lines).strip() or "(no facts recorded yet)"


# ---------------------------------------------------------------------------
# session scope — reuse OpenJarvis SessionStore (pure-python sqlite).
# ---------------------------------------------------------------------------
def show_session(user_id: str, limit: int) -> str:
    from openjarvis.sessions.session import SessionStore

    store = SessionStore()
    try:
        session = store.get_or_create(user_id)
        msgs = session.messages[-limit:] if session.messages else []
        if not msgs:
            return f"No session history for user '{user_id}' yet."
        out = [f"Session '{session.session_id}' — last {len(msgs)} message(s):"]
        for m in msgs:
            out.append(f"  [{m.role}] {m.content[:120]}")
        return "\n".join(out)
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Jarvis memory (Phase 3).")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("remember", help="Store a personal fact.")
    pr.add_argument("key")
    pr.add_argument("value")
    pr.add_argument("--category", "-c", default="notes", choices=VALID_CATEGORIES)

    pf = sub.add_parser("forget", help="Delete a personal fact.")
    pf.add_argument("key")
    pf.add_argument("--category", "-c", default="notes", choices=VALID_CATEGORIES)

    sub.add_parser("show", help="Print all stored personal facts (JSON).")
    sub.add_parser("render", help="Rebuild the USER.md profile block from facts.")

    ps = sub.add_parser("session", help="Show recent session turns.")
    ps.add_argument("--user", default="default")
    ps.add_argument("--limit", type=int, default=10)

    sub.add_parser("code", help="How to query the code graph (Phase 2 MCP).")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    store = FactsStore()

    if args.cmd == "remember":
        print(store.remember(args.key, args.value, args.category))
    elif args.cmd == "forget":
        print(store.forget(args.key, args.category))
    elif args.cmd == "show":
        print(json.dumps(store.load(), indent=2, ensure_ascii=False))
    elif args.cmd == "render":
        path = store.render()
        print(f"Rendered personal facts into {path}")
    elif args.cmd == "session":
        print(show_session(args.user, args.limit))
    elif args.cmd == "code":
        print(
            "code_graph is served by the codebase-memory MCP wired in Phase 2.\n"
            "Ask code questions through the orchestrator, e.g.:\n"
            '  pwsh .\\scripts\\jarvis.ps1 ask --agent operative "Which file defines '
            'SystemPromptBuilder?"\n'
            "Graph UI: codebase-memory-mcp --ui=true --port=9749  (http://localhost:9749)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
