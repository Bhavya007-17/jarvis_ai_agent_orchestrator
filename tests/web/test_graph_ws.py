import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import jarvis_web_api as api  # noqa: E402


def test_graph_ws_rejects_bad_input():
    client = TestClient(api.app)
    with client.websocket_connect("/api/graph") as ws:
        ws.send_json({"task": "", "nodes": [], "edges": []})
        frame = ws.receive_json()
        assert frame["type"] == "error"


def test_graph_ws_streams_frames(monkeypatch):
    async def fake_run_graph(graph, *, emit=None, max_tokens=400, call_node=None):
        emit({"type": "node_start", "node": "a1"})
        emit({"type": "node_end", "node": "a1", "content": "x", "model": "m"})
        emit({"type": "graph_done", "output": "DONE"})
        return {"output": "DONE", "outputs": {}, "models": {}}

    # Bypass validation here — this test targets WS frame forwarding, not
    # validation (covered by test_graph_ws_rejects_bad_input + unit tests).
    # Offline, _known_models() is empty so a synthetic model id won't validate.
    monkeypatch.setattr(api.jarvis_graph, "_validate_graph", lambda g: None)
    monkeypatch.setattr(api.jarvis_graph, "run_graph", fake_run_graph)
    client = TestClient(api.app)
    with client.websocket_connect("/api/graph") as ws:
        ws.send_json({"task": "t",
                      "nodes": [{"id": "a1", "persona": "A", "model": "m"},
                                {"id": "orchestrator", "persona": "Orchestrator"}],
                      "edges": [{"source": "a1", "target": "orchestrator"}]})
        types = []
        while True:
            f = ws.receive_json()
            types.append(f["type"])
            if f["type"] in ("graph_done", "error"):
                break
        assert "node_start" in types and "graph_done" in types


def test_personas_loaded_from_file():
    personas = api._load_personas()
    assert {"architect", "fact-checker"} <= personas
