#!/usr/bin/env python
"""Generate the active OpenJarvis config from .env — NIM via LiteLLM as default.

Keeps .env the single source of truth for model IDs (they drift monthly): this
reads NIM_MODEL_GENERAL / NIM_MODEL_REASONING from .env and writes
``~/.openjarvis/config.toml`` so ``jarvis ask`` defaults to NVIDIA NIM through
LiteLLM's native ``nvidia_nim/`` provider. Re-run after editing .env model IDs.

Usage:
    uv run python scripts/setup_config.py

Why ``nvidia_nim/``: OpenJarvis's engine discovery instantiates LiteLLMEngine
with no api_base (see engine/_discovery.py:_make_engine), so the OpenAI-compat
``api_base`` route can't be wired through config alone. LiteLLM's native NIM
provider needs no api_base — it knows the endpoint and reads NVIDIA_NIM_API_KEY
(set by scripts/jarvis.ps1 from NVIDIA_API_KEY).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from openjarvis.core.paths import get_config_dir

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

PROVIDER = "nvidia_nim"  # LiteLLM native NVIDIA NIM provider prefix


def _find_cbm() -> str | None:
    """Locate the codebase-memory-mcp binary (Phase 2 MCP drop-in).

    Order: ``CBM_BIN`` env override → PATH (``shutil.which``) → the
    default Windows install dir used by the project's ``install.ps1``
    (``%LOCALAPPDATA%\\Programs\\codebase-memory-mcp``). Returns the
    absolute path, or ``None`` if not installed — the loader spawns this
    via ``subprocess.Popen`` with no shell, so an absolute path is
    required (it does not resolve PATH the way a shell would).
    """
    override = os.environ.get("CBM_BIN", "").strip()
    if override and Path(override).exists():
        return str(Path(override).resolve())

    on_path = shutil.which("codebase-memory-mcp")
    if on_path:
        return str(Path(on_path).resolve())

    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        candidate = (
            Path(local)
            / "Programs"
            / "codebase-memory-mcp"
            / "codebase-memory-mcp.exe"
        )
        if candidate.exists():
            return str(candidate.resolve())
    return None


def _has_agent_reach() -> bool:
    """True if the agent-reach MCP server is importable in this interpreter."""
    import importlib.util

    return (
        importlib.util.find_spec("agent_reach") is not None
        and importlib.util.find_spec("mcp") is not None
    )


def build_mcp_servers() -> list[dict]:
    """Build the ``config.tools.mcp.servers`` list for Phase 2.

    Wires two stdio MCP servers that OpenJarvis's ``mcp/loader.py`` will
    spawn on demand:

    * ``codebase-memory`` — code knowledge-graph (14 tools). Arg-free so
      per-``ask`` spawns don't contend for the :9749 graph-UI port; the
      UI is run as a separate long-lived process.
    * ``agent-reach`` — internet/GitHub glue layer; its MCP server
      exposes ``get_status`` (real fetches go through gh / Jina).

    Each server is auto-detected; missing ones are skipped (with a
    warning) rather than failing config generation.
    """
    servers: list[dict] = []

    cbm = _find_cbm()
    if cbm:
        servers.append({"name": "codebase-memory", "command": cbm, "args": []})
        print(f"[ok] MCP server 'codebase-memory' -> {cbm}")
    else:
        print(
            "[warn] codebase-memory-mcp not found "
            "(set CBM_BIN or run _vendor/codebase-memory-mcp/install.ps1) "
            "— skipping that MCP server.",
            file=sys.stderr,
        )

    if _has_agent_reach():
        servers.append(
            {
                "name": "agent-reach",
                "command": sys.executable,
                "args": ["-m", "agent_reach.integrations.mcp_server"],
            }
        )
        print(f"[ok] MCP server 'agent-reach' -> {sys.executable} -m agent_reach...")
    else:
        print(
            "[warn] agent_reach / mcp not importable in this interpreter "
            "— skipping that MCP server.",
            file=sys.stderr,
        )

    return servers


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value or "REPLACE_ME" in value:
        print(f"[FAIL] {name} is missing or a placeholder in .env.", file=sys.stderr)
        sys.exit(1)
    return value


def render_config(general: str, reasoning: str, servers: list[dict]) -> str:
    """Render the minimal NIM-via-LiteLLM config.toml body.

    ``servers`` is serialized to a JSON array and embedded in a TOML
    single-quoted *literal* string so Windows backslash paths survive
    untouched: ``json.dumps`` escapes ``\\`` → ``\\\\`` and the literal
    string preserves it, so OpenJarvis's ``json.loads(servers)`` in
    ``mcp/loader.py`` restores the original path.
    """
    # TOML literal strings cannot contain a single quote; paths never do,
    # but guard anyway by falling back to an empty list if one sneaks in.
    servers_json = json.dumps(servers)
    if "'" in servers_json:
        servers_json = "[]"

    return f"""# Jarvis active config — generated by scripts/setup_config.py from .env.
# Do not hand-edit model IDs here; edit .env and re-run the generator.

[engine]
default = "litellm"

[intelligence]
preferred_engine = "litellm"
default_model = "{PROVIDER}/{general}"
fallback_model = "{PROVIDER}/{reasoning}"

[agent]
default_agent = "simple"

[tools.mcp]
enabled = true
servers = '{servers_json}'

[server]
host = "127.0.0.1"
port = 8000
"""


def main() -> None:
    if load_dotenv is not None:
        load_dotenv()

    general = _require("NIM_MODEL_GENERAL")
    reasoning = _require("NIM_MODEL_REASONING")

    servers = build_mcp_servers()

    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"

    if config_path.exists():
        backup = config_path.with_suffix(".toml.bak")
        shutil.copy2(config_path, backup)
        print(f"[ok] Backed up existing config -> {backup}")

    body = render_config(general, reasoning, servers)
    config_path.write_text(body, encoding="utf-8")

    print(f"[PASS] Wrote {config_path}")
    print(f"       default_model  = {PROVIDER}/{general}")
    print(f"       fallback_model = {PROVIDER}/{reasoning}")
    print(f"       mcp servers    = {', '.join(s['name'] for s in servers) or '(none)'}")


if __name__ == "__main__":
    main()
