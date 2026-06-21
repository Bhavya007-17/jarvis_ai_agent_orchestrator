"""Phase 8 — ada shell layout persistence (/api/ui-layout)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

import pytest
from fastapi.testclient import TestClient

import jarvis_web_api

client = TestClient(jarvis_web_api.app)


@pytest.fixture
def layout_file(monkeypatch, tmp_path):
    path = tmp_path / "ui_layout.json"
    monkeypatch.setattr(jarvis_web_api, "_layout_path", lambda: path)
    return path


def test_layout_get_default_is_empty(layout_file):
    assert client.get("/api/ui-layout").json() == {"windows": {}}


def test_layout_put_round_trips(layout_file):
    layout = {"windows": {"chat": {"x": 320.0, "y": 180.0, "open": True, "z": 31}}}
    put = client.put("/api/ui-layout", json=layout).json()
    assert put["ok"] is True
    again = client.get("/api/ui-layout").json()
    assert again["windows"]["chat"] == {"x": 320.0, "y": 180.0, "open": True, "z": 31}


def test_layout_rejects_unknown_module(layout_file):
    bad = {"windows": {"wizard": {"x": 1, "y": 2, "open": True, "z": 30}}}
    r = client.put("/api/ui-layout", json=bad).json()
    assert r["ok"] is False and "module" in r["message"]


def test_layout_rejects_non_numeric_coord(layout_file):
    bad = {"windows": {"chat": {"x": "left", "y": 2, "open": True, "z": 30}}}
    r = client.put("/api/ui-layout", json=bad).json()
    assert r["ok"] is False and "x" in r["message"]


def test_layout_rejects_non_bool_open(layout_file):
    bad = {"windows": {"chat": {"x": 1, "y": 2, "open": "yes", "z": 30}}}
    r = client.put("/api/ui-layout", json=bad).json()
    assert r["ok"] is False and "open" in r["message"]


def test_layout_get_tolerates_corrupt_file(layout_file):
    layout_file.write_text("{ not json", encoding="utf-8")
    assert client.get("/api/ui-layout").json() == {"windows": {}}


def test_layout_bad_put_leaves_prior_file_intact(layout_file):
    good = {"windows": {"chat": {"x": 1, "y": 2, "open": True, "z": 30}}}
    client.put("/api/ui-layout", json=good)
    client.put("/api/ui-layout", json={"windows": {"wizard": {"x": 1, "y": 2, "open": True, "z": 30}}})
    assert client.get("/api/ui-layout").json()["windows"]["chat"]["x"] == 1
