"""Phase 6 wake-word + VAD segmentation primitives (lazy, mockable)."""
from __future__ import annotations

import os
from typing import Optional


class WakeWord:
    """Wraps openWakeWord. Feed 16kHz int16 PCM frames; returns wake score."""

    def __init__(self, model_name: Optional[str] = None, threshold: Optional[float] = None):
        self.model_name = model_name or os.environ.get("WAKE_MODEL", "hey_jarvis")
        self.threshold = float(threshold if threshold is not None
                               else os.environ.get("WAKE_THRESHOLD", "0.5"))
        self._model = None

    def _ensure(self):
        if self._model is None:
            from openwakeword.model import Model
            self._model = Model(wakeword_models=[self.model_name], inference_framework="onnx")
        return self._model

    def process(self, frame: bytes) -> float:
        import numpy as np
        scores = self._ensure().predict(np.frombuffer(frame, dtype=np.int16))
        return float(max(scores.values())) if scores else 0.0

    def triggered(self, frame: bytes) -> bool:
        return self.process(frame) >= self.threshold
