#!/usr/bin/env python
"""Verify that the NIM model IDs configured in .env actually exist.

NVIDIA NIM model IDs drift roughly monthly, so a stale ID silently 404s at
call time. This script pings ``GET /v1/models`` on the NIM endpoint with your
``NVIDIA_API_KEY`` and asserts that every role-mapped ID in ``.env`` is present
in the live catalog. It fails loudly (exit code 1) so config drift surfaces at
setup time, not mid-conversation.

Usage:
    uv run python scripts/verify_models.py

Reads (from .env or the process environment):
    NVIDIA_API_KEY                       — required; the nvapi- key
    NIM_MODEL_REASONING / _CODE / _GENERAL
    NIM_COUNCIL_1 / _2 / _3
    NIM_CRITIC                           — role->ID mappings to verify
"""

from __future__ import annotations

import os
import sys

import httpx

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv ships with the inference-litellm extra
    load_dotenv = None

NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Env vars that hold a NIM model ID we depend on. Order is display order.
ROLE_ENV_VARS = (
    "NIM_MODEL_REASONING",
    "NIM_MODEL_CODE",
    "NIM_MODEL_GENERAL",
    "NIM_COUNCIL_1",
    "NIM_COUNCIL_2",
    "NIM_COUNCIL_3",
    "NIM_CRITIC",
)


def _fail(message: str) -> "NoReturn":  # type: ignore[name-defined]
    """Print a loud error and exit non-zero."""
    print(f"\n[FAIL] {message}", file=sys.stderr)
    sys.exit(1)


def fetch_catalog(api_key: str) -> set[str]:
    """Return the set of model IDs the NIM endpoint currently serves."""
    url = f"{NIM_BASE_URL}/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        resp = httpx.get(url, headers=headers, timeout=30.0)
    except httpx.HTTPError as exc:
        _fail(f"Could not reach {url}: {exc}")
    if resp.status_code == 401:
        _fail("NVIDIA_API_KEY was rejected (HTTP 401). Check the key in .env.")
    if resp.status_code != 200:
        _fail(f"GET /v1/models returned HTTP {resp.status_code}: {resp.text[:300]}")
    try:
        data = resp.json().get("data", [])
    except ValueError as exc:
        _fail(f"Response was not valid JSON: {exc}")
    ids = {entry.get("id", "") for entry in data if entry.get("id")}
    if not ids:
        _fail("NIM returned an empty model list — unexpected; aborting.")
    return ids


def collect_configured() -> dict[str, str]:
    """Return {env_var: model_id} for every configured role var that is set."""
    configured: dict[str, str] = {}
    for var in ROLE_ENV_VARS:
        value = os.environ.get(var, "").strip()
        if value:
            configured[var] = value
    return configured


def main() -> None:
    if load_dotenv is not None:
        load_dotenv()  # picks up ./.env without overriding real process env

    api_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not api_key or "REPLACE_ME" in api_key:
        _fail("NVIDIA_API_KEY is missing or still a placeholder in .env.")

    catalog = fetch_catalog(api_key)
    print(f"[ok] NIM endpoint reachable — {len(catalog)} models available.")

    configured = collect_configured()
    if not configured:
        _fail("No NIM_MODEL_*/NIM_COUNCIL_*/NIM_CRITIC vars are set in .env.")

    missing: list[tuple[str, str]] = []
    print("\nConfigured role -> model ID:")
    for var, model_id in configured.items():
        present = model_id in catalog
        marker = "OK " if present else "MISSING"
        print(f"  [{marker}] {var:<20} {model_id}")
        if not present:
            missing.append((var, model_id))

    if missing:
        print("\nClosest catalog matches for the missing IDs:")
        for var, model_id in missing:
            org = model_id.split("/", 1)[0] if "/" in model_id else model_id
            hits = sorted(m for m in catalog if m.startswith(org))[:8]
            print(f"  {var} ({model_id}):")
            for h in hits or sorted(catalog)[:8]:
                print(f"      - {h}")
        _fail(
            f"{len(missing)} configured model ID(s) do not exist on NIM. "
            "Update the listed vars in .env to a current ID above."
        )

    print(f"\n[PASS] All {len(configured)} configured NIM model IDs exist.")


if __name__ == "__main__":
    main()
