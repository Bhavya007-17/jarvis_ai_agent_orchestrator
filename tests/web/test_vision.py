import importlib, sys, os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
jv = importlib.import_module("jarvis_vision")


def test_compare_identical_vectors_matches():
    v = [0.1, 0.2, 0.3, 0.4]
    match, sim = jv.compare_landmarks(v, v)
    assert match is True
    assert sim == pytest.approx(1.0, abs=1e-6)


def test_compare_orthogonal_vectors_rejected():
    match, sim = jv.compare_landmarks([1.0, 0.0], [0.0, 1.0])
    assert match is False
    assert sim == pytest.approx(0.0, abs=1e-6)


def test_compare_length_mismatch_zero_norm_and_none_are_safe():
    assert jv.compare_landmarks([1.0, 2.0], [1.0]) == (False, 0.0)
    assert jv.compare_landmarks([0.0, 0.0], [0.0, 0.0]) == (False, 0.0)
    assert jv.compare_landmarks(None, [1.0]) == (False, 0.0)
    assert jv.compare_landmarks([], []) == (False, 0.0)


def test_validate_vector():
    assert jv.validate_vector([1.0, 2.0, 3.0]) is None
    assert jv.validate_vector("nope") is not None
    assert jv.validate_vector([]) is not None
    assert jv.validate_vector([True, False]) is not None      # bools rejected
    assert jv.validate_vector([1.0, float("inf")]) is not None
    assert jv.validate_vector([0.0] * (jv.MAX_DIMS + 1)) is not None


def test_reference_store_roundtrip_and_corruption(tmp_path, monkeypatch):
    monkeypatch.setattr(jv, "_config_dir", lambda: tmp_path)
    store = jv.FaceReferenceStore()
    assert store.enrolled() is False
    assert store.load() is None
    store.save([0.5, 0.6, 0.7])
    data = store.load()
    assert data["vector"] == [0.5, 0.6, 0.7]
    assert data["dims"] == 3
    assert "enrolled_at" in data
    assert store.enrolled() is True
    store.path.write_text("{ not json", encoding="utf-8")
    assert store.load() is None          # corrupt -> None, never raises
    store.save([1.0])
    store.clear()
    assert store.enrolled() is False


def test_lock_store(tmp_path, monkeypatch):
    monkeypatch.setattr(jv, "_config_dir", lambda: tmp_path)
    lock = jv.LockStore()
    assert lock.enabled() is False
    lock.set(True)
    assert lock.enabled() is True
    lock.set(False)
    assert lock.enabled() is False


# ---------------------------------------------------------------------------
# Endpoint tests (Task 2)
# ---------------------------------------------------------------------------
import importlib
from fastapi.testclient import TestClient


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(jv, "_config_dir", lambda: tmp_path)
    web = importlib.import_module("jarvis_web_api")
    return TestClient(web.app)


def test_vision_endpoints_flow(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    # not enrolled yet
    r = client.get("/api/vision/status")
    assert r.json() == {"enrolled": False, "lock_enabled": False}

    # verify before enroll -> no match, never 500
    r = client.post("/api/vision/verify", json={"vector": [0.1, 0.2, 0.3]})
    assert r.json() == {"match": False, "similarity": 0.0}

    # bad enroll payloads rejected
    assert client.post("/api/vision/enroll", json={"vector": "nope"}).json()["ok"] is False
    assert client.post("/api/vision/enroll", json={"vector": [True, False]}).json()["ok"] is False

    # enroll, then status flips
    ref = [0.1, 0.2, 0.3]
    assert client.post("/api/vision/enroll", json={"vector": ref}).json()["ok"] is True
    assert client.get("/api/vision/status").json()["enrolled"] is True

    # matching vector verifies, different vector does not
    assert client.post("/api/vision/verify", json={"vector": ref}).json()["match"] is True
    assert client.post("/api/vision/verify", json={"vector": [3.0, -1.0, 0.0]}).json()["match"] is False

    # lock toggle
    assert client.put("/api/vision/lock", json={"enabled": True}).json()["lock_enabled"] is True
    assert client.get("/api/vision/status").json()["lock_enabled"] is True


def test_vision_never_returns_the_stored_vector(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    ref = [0.123456, 0.654321, 0.314159]
    client.post("/api/vision/enroll", json={"vector": ref})
    bodies = [
        client.get("/api/vision/status").text,
        client.post("/api/vision/enroll", json={"vector": ref}).text,
        client.post("/api/vision/verify", json={"vector": ref}).text,
        client.put("/api/vision/lock", json={"enabled": True}).text,
    ]
    for body in bodies:
        assert "0.123456" not in body
        assert "0.654321" not in body
