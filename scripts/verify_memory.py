#!/usr/bin/env python
"""Phase 3 gate check — verify the three memory scopes work end-to-end.

Each scope is exercised through the *real* OpenJarvis machinery, in isolated
temp locations so the user's ~/.openjarvis state is never touched:

  personal_facts : store a fact with the ported FactsStore, render it, then
                   build the actual ``SystemPromptBuilder`` (the same class
                   cli/ask.py uses) against that USER.md and assert the fact
                   appears in the built system prompt → proves a durable fact
                   is recalled on a later turn.
  session        : round-trip messages through OpenJarvis ``SessionStore``
                   (sqlite) and assert they are recalled after reopen.
  code_graph     : assert the codebase-memory MCP server is configured in the
                   active config, so code questions route to the Phase-2 graph
                   (full tool discovery is covered by verify_mcp.py).

Usage:
    uv run python scripts/verify_memory.py

Exit 0 = PASS (all three scopes), 1 = FAIL.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # import jarvis_memory

import jarvis_memory as jm  # noqa: E402
from openjarvis.core.config import MemoryFilesConfig, load_config  # noqa: E402
from openjarvis.prompt.builder import SystemPromptBuilder  # noqa: E402

FACT_KEY = "favorite_language"
FACT_VALUE = "Python (typed, with ruff)"


def check_personal_facts() -> bool:
    """Durable fact -> USER.md -> injected into the built system prompt."""
    with tempfile.TemporaryDirectory() as tmp:
        facts_path = Path(tmp) / "personal_facts.json"
        user_md = Path(tmp) / "USER.md"
        # Point the module's render target at our temp USER.md (full fidelity
        # with the real path config.memory_files would use, no pollution).
        jm.USER_MD_PATH = user_md

        store = jm.FactsStore(path=facts_path)
        store.remember(FACT_KEY, FACT_VALUE, category="preferences")

        # Reload from disk in a fresh store == a *later turn* reading state.
        reloaded = jm.FactsStore(path=facts_path).load()
        if reloaded["preferences"].get(FACT_KEY, {}).get("value") != FACT_VALUE:
            print("[FAIL] personal_facts: fact not persisted to JSON", file=sys.stderr)
            return False

        if not user_md.exists() or FACT_VALUE not in user_md.read_text(encoding="utf-8"):
            print("[FAIL] personal_facts: fact not rendered into USER.md", file=sys.stderr)
            return False

        # The exact wiring cli/ask.py uses: build the prompt with USER.md.
        builder = SystemPromptBuilder(
            agent_template="You are Jarvis.",
            memory_files_config=MemoryFilesConfig(user_path=str(user_md)),
        )
        prompt = builder.build()
        if FACT_VALUE not in prompt or "User Profile" not in prompt:
            print(
                "[FAIL] personal_facts: fact not injected into system prompt",
                file=sys.stderr,
            )
            return False

        # forget removes it again.
        jm.FactsStore(path=facts_path).forget(FACT_KEY, category="preferences")
        if jm.FactsStore(path=facts_path).load()["preferences"].get(FACT_KEY):
            print("[FAIL] personal_facts: forget did not remove the fact", file=sys.stderr)
            return False

    print(f"[ok] personal_facts: '{FACT_KEY}' stored, rendered, injected, forgotten.")
    return True


def check_session() -> bool:
    """Messages persist across a SessionStore reopen (later turn)."""
    from openjarvis.sessions.session import SessionStore

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "sessions.db"
        store = SessionStore(db_path=db)
        store2 = None
        try:
            session = store.get_or_create("gate-user")
            store.save_message(session.session_id, "user", "Remember I prefer dark mode.")
            store.save_message(session.session_id, "assistant", "Noted — dark mode it is.")

            # Reopen the db == a later turn.
            store2 = SessionStore(db_path=db)
            again = store2.get_or_create("gate-user")
            contents = [m.content for m in again.messages]
            if "Remember I prefer dark mode." not in contents:
                print("[FAIL] session: message not recalled after reopen", file=sys.stderr)
                return False
        finally:
            # Close sqlite connections so Windows can remove the temp db.
            for s in (store, store2):
                conn = getattr(s, "_conn", None)
                if conn is not None:
                    conn.close()

    print(f"[ok] session: {len(contents)} message(s) recalled across reopen.")
    return True


def check_code_graph() -> bool:
    """The code-graph MCP server is configured, so code Qs route to it."""
    config = load_config()
    raw = getattr(config.tools.mcp, "servers", "") or "[]"
    try:
        servers = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"[FAIL] code_graph: tools.mcp.servers is not valid JSON ({exc})", file=sys.stderr)
        return False
    names = {s.get("name", "") for s in servers if isinstance(s, dict)}
    if "codebase-memory" not in names:
        print(
            "[FAIL] code_graph: 'codebase-memory' MCP server not in active config "
            "(run scripts/setup_config.py). Found: " + (", ".join(sorted(names)) or "none"),
            file=sys.stderr,
        )
        return False
    print("[ok] code_graph: 'codebase-memory' MCP server configured (Phase 2 wiring).")
    return True


def main() -> None:
    print("Phase 3 memory gate — three scopes:\n")
    results = {
        "personal_facts": check_personal_facts(),
        "session": check_session(),
        "code_graph": check_code_graph(),
    }
    print()
    if all(results.values()):
        print("[PASS] All three memory scopes verified.")
        sys.exit(0)
    failed = [k for k, v in results.items() if not v]
    print(f"[FAIL] Phase 3 gate incomplete: {', '.join(failed)}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
