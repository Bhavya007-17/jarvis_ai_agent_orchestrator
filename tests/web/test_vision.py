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
