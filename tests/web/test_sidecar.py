import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
from fastapi.testclient import TestClient
import jarvis_web_api

client = TestClient(jarvis_web_api.app)

def test_health_ok():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_models_lists_task_map_and_models(monkeypatch):
    monkeypatch.setattr(
        jarvis_web_api.jarvis_router, "task_model_map",
        lambda: {"reasoning": "nemotron", "code": "qwen", "general": "llama"},
    )
    r = client.get("/api/models")
    body = r.json()
    assert body["task_map"]["code"] == "qwen"
    assert "auto" in body["models"]
    assert "qwen" in body["models"]


import asyncio


class _FakeEngine:
    def __init__(self, pieces=None, raise_on_stream=False):
        self._pieces = pieces or ["Hel", "lo"]
        self._raise = raise_on_stream

    async def stream(self, messages, model=None, **kw):
        if self._raise:
            raise RuntimeError("stream boom")
        for p in self._pieces:
            yield p


def _drain(gen):
    async def run():
        return [f async for f in gen]
    return asyncio.run(run())


def test_stream_chat_happy_path(monkeypatch):
    monkeypatch.setattr(jarvis_web_api, "LiteLLMEngine", lambda: _FakeEngine(["Hi ", "there"]))
    monkeypatch.setattr(jarvis_web_api.jarvis_router, "build_ladder",
                        lambda tt: [("NIM-A", "nvidia_nim/x")])
    frames = _drain(jarvis_web_api.stream_chat("hello", "auto"))
    types = [f["type"] for f in frames]
    assert types[0] == "rung"
    assert "chunk" in types
    assert frames[-1] == {"type": "done", "content": "Hi there"}


def test_stream_chat_falls_back_on_stream_error(monkeypatch):
    monkeypatch.setattr(jarvis_web_api, "LiteLLMEngine", lambda: _FakeEngine(raise_on_stream=True))
    monkeypatch.setattr(jarvis_web_api.jarvis_router, "build_ladder",
                        lambda tt: [("NIM-A", "nvidia_nim/x")])
    monkeypatch.setattr(jarvis_web_api.jarvis_router, "complete_with_fallback",
                        lambda *a, **k: {"content": "fallback answer", "model": "ollama/q", "rung": "local", "path": []})
    frames = _drain(jarvis_web_api.stream_chat("hello", "auto"))
    assert frames[-1] == {"type": "done", "content": "fallback answer"}
    assert any(f["type"] == "rung" and f["rung"] == "local" for f in frames)


def test_chat_ws_rejects_invalid_json():
    with TestClient(jarvis_web_api.app).websocket_connect("/api/chat") as ws:
        ws.send_text("not json")
        f = ws.receive_json()
        assert f["type"] == "error"
        assert "JSON" in f["detail"]
