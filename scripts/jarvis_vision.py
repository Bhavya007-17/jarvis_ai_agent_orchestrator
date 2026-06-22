"""Phase 10 - Vision core: ported face-landmark compare + presence-only stores.

The browser (MediaPipe WASM) extracts landmark vectors; this module owns only the
security-relevant decision (cosine-similarity compare, ported verbatim from
_vendor/ada_v2/backend/authenticator.py:86-108) and the server-side persistence of the
enrolled reference vector - which is treated like a secret and never returned to a client.
Pure numpy: no mediapipe/opencv Python dependency.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

MAX_DIMS = 4096  # face mesh is ~1404-1434 floats; generous upper bound


def _config_dir() -> Path:
    from openjarvis.core.paths import get_config_dir
    return get_config_dir()


def compare_landmarks(ref, cur, threshold: float = 0.15):
    """Cosine similarity of two flattened landmark vectors.

    Returns (is_match, similarity). is_match = similarity > (1 - threshold).
    Any degenerate input (None/empty/length-mismatch/zero-norm) -> (False, 0.0).
    """
    if ref is None or cur is None:
        return (False, 0.0)
    a = np.asarray(ref, dtype=np.float64).ravel()
    b = np.asarray(cur, dtype=np.float64).ravel()
    if a.size == 0 or b.size == 0 or a.size != b.size:
        return (False, 0.0)
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return (False, 0.0)
    sim = float(np.dot(a, b) / (na * nb))
    return (sim > (1.0 - threshold), sim)


def validate_vector(vector) -> str | None:
    """Return an error string, or None if the vector is a sane numeric list."""
    if not isinstance(vector, list):
        return "vector must be a list"
    if not (1 <= len(vector) <= MAX_DIMS):
        return f"vector length must be between 1 and {MAX_DIMS}"
    for v in vector:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return "vector elements must be numbers"
        if not math.isfinite(float(v)):
            return "vector elements must be finite"
    return None


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)  # atomic on the same filesystem


class FaceReferenceStore:
    """Stores the single enrolled face vector. Path resolved lazily so tests can
    monkeypatch _config_dir."""

    def __init__(self, path: Path | None = None):
        self._path = path

    @property
    def path(self) -> Path:
        return self._path or (_config_dir() / "face_reference.json")

    def load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict) or not isinstance(data.get("vector"), list):
            return None
        return data

    def enrolled(self) -> bool:
        return self.load() is not None

    def save(self, vector) -> None:
        _atomic_write_json(self.path, {
            "vector": list(vector),
            "dims": len(vector),
            "enrolled_at": datetime.now(timezone.utc).isoformat(),
        })

    def clear(self) -> None:
        try:
            self.path.unlink()
        except OSError:
            pass


class LockStore:
    """Boolean flag: should the full-screen AuthLock overlay show on startup."""

    def __init__(self, path: Path | None = None):
        self._path = path

    @property
    def path(self) -> Path:
        return self._path or (_config_dir() / "vision_lock.json")

    def enabled(self) -> bool:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return bool(data.get("enabled", False))
        except (OSError, ValueError):
            return False

    def set(self, enabled) -> None:
        _atomic_write_json(self.path, {"enabled": bool(enabled)})
