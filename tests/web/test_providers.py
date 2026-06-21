"""Phase 7 (E) — provider keys from anywhere.

Covers jarvis_providers (presence / model listing / key validation / atomic
.env write + live os.environ) and the two sidecar endpoints. The cardinal rule
under test: a key value is NEVER returned by any response — only presence
booleans.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

import pytest
from fastapi.testclient import TestClient

import jarvis_providers
import jarvis_web_api

client = TestClient(jarvis_web_api.app)


@pytest.fixture
def env_file(monkeypatch, tmp_path):
    """Point the writer at a throwaway .env and clear provider env vars."""
    path = tmp_path / ".env"
    monkeypatch.setattr(jarvis_providers, "_env_path", lambda: path)
    for spec in jarvis_providers.PROVIDERS.values():
        monkeypatch.delenv(spec["key_var"], raising=False)
        monkeypatch.delenv(spec["models_var"], raising=False)
    return path


# --------------------------------------------------------------------------- #
# presence — booleans only, driven by os.environ                              #
# --------------------------------------------------------------------------- #
def test_presence_all_absent_by_default(env_file):
    pres = jarvis_providers.presence()
    assert set(pres) == set(jarvis_providers.PROVIDERS)
    assert all(v is False for v in pres.values())


def test_presence_true_when_key_set(env_file, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123456789")
    assert jarvis_providers.presence()["openai"] is True
    assert jarvis_providers.presence()["anthropic"] is False


def test_presence_blank_key_is_absent(env_file, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "   ")
    assert jarvis_providers.presence()["openai"] is False


# --------------------------------------------------------------------------- #
# provider_models — only enabled providers, comma-split, prefix-carrying       #
# --------------------------------------------------------------------------- #
def test_provider_models_empty_without_keys(env_file):
    assert jarvis_providers.provider_models() == []


def test_provider_models_lists_only_enabled(env_file, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-ok-123456")
    monkeypatch.setenv("OPENAI_MODELS", "openai/gpt-4.1-mini, openai/gpt-4.1")
    # anthropic has models declared but NO key -> excluded
    monkeypatch.setenv("ANTHROPIC_MODELS", "anthropic/claude-opus-4-8")
    models = jarvis_providers.provider_models()
    assert models == ["openai/gpt-4.1-mini", "openai/gpt-4.1"]


# --------------------------------------------------------------------------- #
# validate_key — shape hardening                                              #
# --------------------------------------------------------------------------- #
def test_validate_key_accepts_plausible_key():
    assert jarvis_providers.validate_key("openai", "sk-abcDEF123456") is None


def test_validate_key_rejects_unknown_provider():
    assert "unknown provider" in jarvis_providers.validate_key("evil", "sk-x")


def test_validate_key_rejects_empty():
    assert jarvis_providers.validate_key("openai", "   ") is not None


@pytest.mark.parametrize("bad", ["short", "has space inside", "line\nbreak", "tab\there"])
def test_validate_key_rejects_malformed(bad):
    assert jarvis_providers.validate_key("openai", bad) is not None


# --------------------------------------------------------------------------- #
# set_key — atomic .env write + live os.environ + presence-only return         #
# --------------------------------------------------------------------------- #
def test_set_key_writes_env_and_live_environ(env_file, monkeypatch):
    out = jarvis_providers.set_key("anthropic", "sk-ant-abc123456789")
    assert out["anthropic"] is True
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-abc123456789"
    assert "ANTHROPIC_API_KEY=sk-ant-abc123456789" in env_file.read_text(encoding="utf-8")
    # the return is presence booleans only — never the key value
    assert "sk-ant-abc123456789" not in str(out)


def test_set_key_uncomments_existing_placeholder(env_file, monkeypatch):
    env_file.write_text("# OPENAI_API_KEY=\nNIM_MODEL_GENERAL=meta/x\n", encoding="utf-8")
    jarvis_providers.set_key("openai", "sk-live-987654321")
    text = env_file.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=sk-live-987654321" in text
    assert "# OPENAI_API_KEY=" not in text           # placeholder replaced, not duplicated
    assert text.count("OPENAI_API_KEY=") == 1
    assert "NIM_MODEL_GENERAL=meta/x" in text         # untouched lines preserved


def test_set_key_replaces_not_appends(env_file, monkeypatch):
    jarvis_providers.set_key("groq", "gsk-first-1234567")
    jarvis_providers.set_key("groq", "gsk-second-7654321")
    text = env_file.read_text(encoding="utf-8")
    assert text.count("GROQ_API_KEY=") == 1
    assert "gsk-second-7654321" in text


# --------------------------------------------------------------------------- #
# /api/providers — presence GET, write POST, never leak the key                #
# --------------------------------------------------------------------------- #
def test_get_providers_returns_presence_only(env_file):
    body = client.get("/api/providers").json()
    assert set(body["providers"]) == set(jarvis_providers.PROVIDERS)
    assert all(v is False for v in body["providers"].values())


def test_post_provider_writes_and_hides_key(env_file):
    r = client.post("/api/providers", json={"provider": "openai",
                                            "key": "sk-secret-abcdef123"}).json()
    assert r["ok"] is True
    assert r["providers"]["openai"] is True
    assert "sk-secret-abcdef123" not in str(r)        # key never echoed back
    assert client.get("/api/providers").json()["providers"]["openai"] is True


def test_post_provider_rejects_bad_key(env_file):
    r = client.post("/api/providers", json={"provider": "openai", "key": "x"}).json()
    assert r["ok"] is False and "message" in r


def test_post_provider_rejects_unknown_provider(env_file):
    r = client.post("/api/providers", json={"provider": "evil", "key": "sk-123456789"}).json()
    assert r["ok"] is False


# --------------------------------------------------------------------------- #
# /api/models — enabled provider models appear in the dropdown set             #
# --------------------------------------------------------------------------- #
def test_models_includes_enabled_provider_models(env_file, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-key-123456")
    monkeypatch.setenv("ANTHROPIC_MODELS", "anthropic/claude-opus-4-8")
    body = client.get("/api/models").json()
    assert "anthropic/claude-opus-4-8" in body["models"]
