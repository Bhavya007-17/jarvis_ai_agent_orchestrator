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
