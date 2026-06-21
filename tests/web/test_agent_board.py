"""Agent Board (Slice B) — roster council, board persistence, WS passthrough."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

import pytest
from fastapi.testclient import TestClient

import jarvis_council
import jarvis_web_api

client = TestClient(jarvis_web_api.app)


# --------------------------------------------------------------------------- #
# _build_roster — validation + cap                                            #
# --------------------------------------------------------------------------- #
@pytest.fixture
def known_models(monkeypatch):
    models = {"m1", "m2", "m3", "m4", "reason"}
    monkeypatch.setattr(jarvis_council, "_known_models", lambda: models)
    return models


def test_build_roster_normalizes_triples(known_models):
    team = jarvis_council._build_roster(
        [{"persona": "Architect", "lens": "structure", "model": "m1"},
         {"persona": "Coder", "lens": "code", "model": "m2"}])
    assert team == [("Architect", "structure", "m1"), ("Coder", "code", "m2")]


def test_build_roster_caps_at_three(known_models):
    roster = [{"persona": f"P{i}", "lens": "x", "model": "m1"} for i in range(5)]
    assert len(jarvis_council._build_roster(roster)) == 3


def test_build_roster_rejects_unknown_model(known_models):
    with pytest.raises(ValueError, match="unknown roster model"):
        jarvis_council._build_roster([{"persona": "X", "model": "evil/model"}])


def test_build_roster_requires_persona_and_model(known_models):
    with pytest.raises(ValueError, match="requires"):
        jarvis_council._build_roster([{"persona": "", "model": "m1"}])
    with pytest.raises(ValueError, match="requires"):
        jarvis_council._build_roster([{"persona": "X", "model": ""}])


def test_build_roster_rejects_empty(known_models):
    with pytest.raises(ValueError, match="empty"):
        jarvis_council._build_roster([])


# --------------------------------------------------------------------------- #
# run_council — roster path vs default path                                    #
# --------------------------------------------------------------------------- #
def _capture_voices(monkeypatch):
    """Replace the network-bound `voice` with a recorder; return the call log."""
    calls = []

    def fake_voice(label, messages, ladder, *, max_tokens, extra_body=None,
                   stream=True, emit=None):
        calls.append({"label": label, "primary": ladder[0][1],
                      "system": messages[0].content})
        return {"content": f"out::{label}", "model": ladder[0][1],
                "rung": "NIM-A", "path": []}

    monkeypatch.setattr(jarvis_council, "voice", fake_voice)
    return calls


def test_run_council_roster_overrides_personas_and_models(monkeypatch, known_models):
    monkeypatch.setenv("NIM_MODEL_REASONING", "reason")
    calls = _capture_voices(monkeypatch)
    jarvis_council.run_council(
        "design a cache", stream=False, execute=False,
        roster=[{"persona": "Coder", "lens": "write tight code", "model": "m2"},
                {"persona": "Researcher", "lens": "gather evidence", "model": "m3"}])
    proposers = [c for c in calls if c["label"].startswith("PROPOSAL")]
    assert [c["label"] for c in proposers] == \
        ["PROPOSAL 1 — Coder", "PROPOSAL 2 — Researcher"]
    # the agent's lens flows into the proposer's system prompt
    assert "write tight code" in proposers[0]["system"]
    # primary rung is the agent's own model (nim-prefixed)
    assert proposers[0]["primary"].endswith("/m2")


def test_run_council_default_path_unchanged(monkeypatch):
    monkeypatch.setenv("NIM_MODEL_REASONING", "reason")
    monkeypatch.setattr(jarvis_council, "council_models", lambda: ["a", "b", "c"])
    calls = _capture_voices(monkeypatch)
    jarvis_council.run_council("design a cache", stream=False, execute=False)
    proposers = [c for c in calls if c["label"].startswith("PROPOSAL")]
    # default personas, in order, from COUNCIL_PERSONAS
    assert [c["label"] for c in proposers] == \
        ["PROPOSAL 1 — Pragmatist", "PROPOSAL 2 — Architect", "PROPOSAL 3 — Skeptic"]
    assert proposers[1]["primary"].endswith("/b")


# --------------------------------------------------------------------------- #
# /api/board — persistence + validation                                       #
# --------------------------------------------------------------------------- #
@pytest.fixture
def board_file(monkeypatch, tmp_path):
    path = tmp_path / "board.json"
    monkeypatch.setattr(jarvis_web_api, "_board_path", lambda: path)
    monkeypatch.setattr(jarvis_web_api.jarvis_council, "_known_models",
                        lambda: {"nvidia/x", "nvidia/y"})
    return path


def test_board_get_default_is_empty(board_file):
    body = client.get("/api/board").json()
    assert body == {"nodes": [], "edges": [], "models": {}}


def test_board_put_round_trips(board_file):
    layout = {
        "nodes": [{"id": "n1", "persona": "architect", "model": "nvidia/x",
                   "x": 10, "y": 20, "benched": False}],
        "edges": [{"id": "e1", "source": "orchestrator", "target": "n1"}],
        "models": {"architect": "nvidia/x"},
    }
    put = client.put("/api/board", json=layout).json()
    assert put["ok"] is True
    again = client.get("/api/board").json()
    assert again["nodes"][0]["persona"] == "architect"
    assert again["edges"][0]["target"] == "n1"


def test_board_put_rejects_unknown_persona(board_file):
    bad = {"nodes": [{"id": "n1", "persona": "wizard", "model": "nvidia/x"}],
           "edges": [], "models": {}}
    r = client.put("/api/board", json=bad).json()
    assert r["ok"] is False and "persona" in r["message"]


def test_board_put_rejects_unknown_model(board_file):
    bad = {"nodes": [{"id": "n1", "persona": "coder", "model": "evil/model"}],
           "edges": [], "models": {}}
    r = client.put("/api/board", json=bad).json()
    assert r["ok"] is False and "model" in r["message"]


def test_board_get_tolerates_corrupt_file(board_file):
    board_file.write_text("{ this is not json", encoding="utf-8")
    assert client.get("/api/board").json() == {"nodes": [], "edges": [], "models": {}}


# --------------------------------------------------------------------------- #
# /api/council WS — forwards a roster                                          #
# --------------------------------------------------------------------------- #
def test_council_ws_forwards_roster(monkeypatch):
    seen = {}

    def fake_run_council(task, *, stream, execute, max_tokens, emit, roster=None):
        seen["roster"] = roster
        emit({"type": "council_done", "voices": ["m2"], "executor": None})

    monkeypatch.setattr(jarvis_web_api.jarvis_council, "run_council", fake_run_council)
    with client.websocket_connect("/api/council") as ws:
        ws.send_json({"task": "plan it",
                      "roster": [{"persona": "Coder", "lens": "x", "model": "m2"}]})
        while ws.receive_json()["type"] != "council_done":
            pass
    assert seen["roster"] == [{"persona": "Coder", "lens": "x", "model": "m2"}]


def test_council_ws_rejects_non_list_roster(monkeypatch):
    with client.websocket_connect("/api/council") as ws:
        ws.send_json({"task": "plan it", "roster": "not-a-list"})
        f = ws.receive_json()
    assert f["type"] == "error" and "roster" in f["detail"]
