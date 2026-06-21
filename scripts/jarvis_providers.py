#!/usr/bin/env python
"""Provider keys from anywhere (Phase 7 / Slice E).

Lets the UI paste an OpenAI / Anthropic / Groq / OpenRouter / Mistral key and
have that provider's models become selectable everywhere — chat, council,
board, (later) Clicky — with **no restart**:

  - The key is written into the project ``.env`` (atomic, like ``_write_board``)
    AND mirrored into ``os.environ`` live so LiteLLMEngine picks it up at once.
  - Model ids are NEVER hardcoded: each provider's selectable ids come from a
    comma-list env var (``OPENAI_MODELS`` etc.), already carrying the LiteLLM
    provider prefix (``openai/gpt-4.1-mini``) exactly like ``GEMINI_FALLBACK_MODEL``.

Cardinal security rule (mirrors CLAUDE.md "never echo a secret"): no function
here ever returns a key value. ``presence()`` reports booleans only; the value
lives solely in ``.env`` / ``os.environ``.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# Provider registry. ``key_var`` is the env/.env name LiteLLM authenticates with
# natively; ``models_var`` is the comma-list of selectable ids; ``prefix`` is the
# LiteLLM route those ids carry (used to keep _ladder_for from re-prefixing them).
PROVIDERS: dict[str, dict[str, str]] = {
    "openai":     {"key_var": "OPENAI_API_KEY",     "models_var": "OPENAI_MODELS",     "prefix": "openai/"},
    "anthropic":  {"key_var": "ANTHROPIC_API_KEY",  "models_var": "ANTHROPIC_MODELS",  "prefix": "anthropic/"},
    "groq":       {"key_var": "GROQ_API_KEY",       "models_var": "GROQ_MODELS",       "prefix": "groq/"},
    "openrouter": {"key_var": "OPENROUTER_API_KEY", "models_var": "OPENROUTER_MODELS", "prefix": "openrouter/"},
    "mistral":    {"key_var": "MISTRAL_API_KEY",    "models_var": "MISTRAL_MODELS",    "prefix": "mistral/"},
}

# A usable key is printable ASCII, no spaces/controls, sane length. Deliberately
# LOOSE: per-provider prefixes (sk-, sk-ant-, gsk_) drift, so we reject only what
# would be malformed or could corrupt the .env line — not "wrong-looking" keys.
# (Tightening to a per-provider prefix is a real security/UX trade-off seam:
#  stricter catches typos but breaks when a provider rotates its prefix scheme.)
_KEY_RE = re.compile(r"^[\x21-\x7e]{8,512}$")


def _env_path() -> Path:
    """The project-root ``.env`` (scripts/ is one level down)."""
    return Path(__file__).resolve().parents[1] / ".env"


def presence() -> dict[str, bool]:
    """Per-provider configured-or-not — booleans ONLY, never the key value."""
    return {name: bool(os.environ.get(spec["key_var"], "").strip())
            for name, spec in PROVIDERS.items()}


def provider_models() -> list[str]:
    """Prefix-carrying model ids for every provider that currently has a key.

    Ids come from the provider's ``*_MODELS`` comma-list in ``.env`` (never
    hardcoded). Providers without a key are skipped so the dropdown only offers
    models that can actually be served.
    """
    pres = presence()
    out: list[str] = []
    for name, spec in PROVIDERS.items():
        if not pres[name]:
            continue
        raw = os.environ.get(spec["models_var"], "").strip()
        for mid in raw.split(","):
            mid = mid.strip()
            if mid:
                out.append(mid)
    return out


def provider_prefixes() -> tuple[str, ...]:
    """LiteLLM route prefixes for all known providers (for ladder prefix logic)."""
    return tuple(spec["prefix"] for spec in PROVIDERS.values())


def validate_key(provider: str, key: str) -> str | None:
    """Return an error message, or None if the key is shape-valid.

    Hardened like the MCP validator: reject anything that isn't a clean,
    single-line printable token so it can't corrupt the ``.env`` file.
    """
    if provider not in PROVIDERS:
        return f"unknown provider {provider!r}"
    key = (key or "").strip()
    if not key:
        return "key is empty"
    if not _KEY_RE.match(key):
        return "key must be 8-512 printable characters with no spaces or newlines"
    return None


def _set_env_var(name: str, value: str) -> None:
    """Atomically upsert ``name=value`` in ``.env``, preserving all other lines.

    Replaces an existing (possibly commented placeholder) ``name=`` line in
    place; otherwise appends. Writes via a temp file + replace so a crash can
    never leave a half-written ``.env`` (same guarantee as ``_write_board``).
    """
    path = _env_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"{name}={value}"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    # Match an active or commented assignment of this exact var (line-anchored,
    # tabs/spaces only around the optional '#', so it never spans lines).
    pattern = re.compile(rf"(?m)^[ \t]*#?[ \t]*{re.escape(name)}=.*$")
    if pattern.search(text):
        text = pattern.sub(lambda _m: line, text, count=1)  # literal repl (keeps backslashes)
    elif text:
        text = text.rstrip("\n") + "\n" + line + "\n"
    else:
        text = line + "\n"
    tmp = path.parent / (path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)  # atomic on the same filesystem


def set_key(provider: str, key: str) -> dict[str, bool]:
    """Persist a provider key to ``.env`` and ``os.environ`` (no restart).

    Returns presence booleans only — the key value is never part of the result.
    Raises ValueError if the provider/key fails ``validate_key`` (the endpoint
    validates first, but this keeps the function safe to call directly).
    """
    err = validate_key(provider, key)
    if err:
        raise ValueError(err)
    key = key.strip()
    key_var = PROVIDERS[provider]["key_var"]
    _set_env_var(key_var, key)
    os.environ[key_var] = key  # live, so LiteLLMEngine authenticates immediately
    return presence()
