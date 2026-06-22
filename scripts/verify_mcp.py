#!/usr/bin/env python
"""Phase 2 gate check — verify MCP servers are discoverable through OpenJarvis.

Exercises the *real* consumption path that ``jarvis ask`` uses:
``load_config()`` → ``load_mcp_tools_from_config(config.tools.mcp)`` (see
``cli/ask.py``). This spawns each configured stdio MCP server, runs the MCP
initialize handshake, and lists its tools — so a PASS here means the
orchestrator will see the same tools at ask-time.

Usage:
    uv run python scripts/verify_mcp.py

Exit code 0 = PASS (both servers contributed their expected tools),
1 = FAIL (a server is missing, failed to start, or exposed no tools).
"""

from __future__ import annotations

import sys

from openjarvis.core.config import load_config
from openjarvis.mcp.loader import load_mcp_tools_from_config

# Minimum tools we expect each registered server to surface. We assert a
# representative subset, not the full set, so an upstream tool rename in one
# server doesn't false-fail the gate for the other.
_EXPECTED = {
    "codebase-memory": {"search_graph", "get_architecture", "index_repository"},
    "agent-reach": {"get_status"},
    # Phase 11 / slice D — the ported action tools (jarvis_tools_mcp.py).
    "jarvis-tools": {"web_search", "weather", "reminder"},
}


def main() -> None:
    config = load_config()
    mcp_cfg = config.tools.mcp

    if not getattr(mcp_cfg, "enabled", False):
        print("[FAIL] tools.mcp.enabled is false in config.toml", file=sys.stderr)
        sys.exit(1)

    print("Loading MCP tools via OpenJarvis loader (this spawns each server)...")
    tools, clients = load_mcp_tools_from_config(mcp_cfg)
    try:
        discovered = sorted(t.spec.name for t in tools)
        print(f"\nDiscovered {len(discovered)} MCP tool(s):")
        for name in discovered:
            print(f"  - {name}")

        discovered_set = set(discovered)
        failures: list[str] = []
        for server, expected in _EXPECTED.items():
            hits = expected & discovered_set
            if hits:
                print(f"\n[ok] '{server}' contributed: {', '.join(sorted(hits))}")
            else:
                failures.append(
                    f"'{server}' contributed none of its expected tools "
                    f"({', '.join(sorted(expected))})"
                )

        if failures:
            print("\n[FAIL] Phase 2 MCP discovery incomplete:", file=sys.stderr)
            for f in failures:
                print(f"  - {f}", file=sys.stderr)
            sys.exit(1)

        print("\n[PASS] All registered MCP servers discoverable through OpenJarvis.")
    finally:
        # Release the spawned subprocess transports (see loader.py note on
        # client lifetime — they would otherwise linger until GC).
        for client in clients:
            try:
                client.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
