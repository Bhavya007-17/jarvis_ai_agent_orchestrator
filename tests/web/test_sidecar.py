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


def test_routing_returns_map_and_ladders(monkeypatch):
    monkeypatch.setattr(jarvis_web_api.jarvis_router, "task_model_map",
                        lambda: {"reasoning": "r", "code": "c", "general": "g"})
    monkeypatch.setattr(jarvis_web_api.jarvis_router, "build_ladder",
                        lambda tt: [("NIM-A", f"nvidia_nim/{tt}"), ("local", "ollama/x")])
    body = client.get("/api/routing").json()
    assert body["task_map"]["code"] == "c"
    assert body["ladders"]["reasoning"][0] == {"label": "NIM-A", "model": "nvidia_nim/reasoning"}
    assert body["graph_url"].startswith("http")


def test_memory_facts_get_and_post(monkeypatch):
    class _FakeStore:
        _data = {"identity": {"name": {"value": "Bhavya", "updated": "2026-06-19"}}}
        def load(self): return self._data
        def remember(self, k, v, c): return f"Remembered: {c}/{k} = {v}"
    monkeypatch.setattr(jarvis_web_api, "FactsStore", _FakeStore)
    g = client.get("/api/memory/facts").json()
    assert g["facts"]["identity"]["name"]["value"] == "Bhavya"
    assert "identity" in g["categories"]
    p = client.post("/api/memory/facts", json={"key": "city", "value": "Blacksburg", "category": "identity"}).json()
    assert p["ok"] and "Remembered" in p["message"]


def test_memory_facts_post_requires_fields():
    r = client.post("/api/memory/facts", json={"key": "", "value": ""}).json()
    assert r["ok"] is False


def test_mcp_servers_list_and_add(monkeypatch):
    store = {"servers": [{"name": "codebase-memory", "command": "cbm", "args": []}]}
    monkeypatch.setattr(jarvis_web_api, "_load_mcp_servers", lambda: list(store["servers"]))
    monkeypatch.setattr(jarvis_web_api, "_write_mcp_servers", lambda s: store.update(servers=s))
    assert client.get("/api/mcp/servers").json()["servers"][0]["name"] == "codebase-memory"
    add = client.post("/api/mcp/servers", json={"name": "extra", "command": "node", "args": ["x.js"]}).json()
    assert add["ok"] and any(s["name"] == "extra" for s in add["servers"])


def test_council_ws_streams_emitted_frames(monkeypatch):
    def fake_run_council(task, *, stream, execute, max_tokens, emit):
        emit({"type": "voice_start", "label": "PROPOSAL 1 — Pragmatist", "model": "m"})
        emit({"type": "voice_chunk", "label": "PROPOSAL 1 — Pragmatist", "content": "step"})
        emit({"type": "voice_end", "label": "PROPOSAL 1 — Pragmatist", "content": "step"})
        emit({"type": "council_done", "voices": ["m"], "executor": None})
    monkeypatch.setattr(jarvis_web_api.jarvis_council, "run_council", fake_run_council)
    with client.websocket_connect("/api/council") as ws:
        ws.send_json({"task": "design a cache"})
        frames = []
        while True:
            f = ws.receive_json()
            frames.append(f)
            if f["type"] == "council_done":
                break
    assert [f["type"] for f in frames] == ["voice_start", "voice_chunk", "voice_end", "council_done"]


def test_mcp_add_server_rejects_shell_and_quotes(monkeypatch):
    monkeypatch.setattr(jarvis_web_api, "_load_mcp_servers", lambda: [])
    monkeypatch.setattr(jarvis_web_api, "_write_mcp_servers", lambda s: None)
    assert client.post("/api/mcp/servers", json={"name": "x", "command": "bash"}).json()["ok"] is False
    assert client.post("/api/mcp/servers", json={"name": "x", "command": "powershell.exe"}).json()["ok"] is False
    assert client.post("/api/mcp/servers", json={"name": "bad name!", "command": "node"}).json()["ok"] is False
    assert client.post("/api/mcp/servers", json={"name": "ok", "command": "node", "args": ["a'b"]}).json()["ok"] is False
    good = client.post("/api/mcp/servers", json={"name": "good-one", "command": "node", "args": ["x.js"]}).json()
    assert good["ok"] is True
