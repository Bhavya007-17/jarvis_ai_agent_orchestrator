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
            try:
                self._model = Model(wakeword_models=[self.model_name], inference_framework="onnx")
            except Exception:  # noqa: BLE001 - model files missing on fresh install
                import openwakeword.utils
                openwakeword.utils.download_models()
                self._model = Model(wakeword_models=[self.model_name], inference_framework="onnx")
        return self._model

    def process(self, frame: bytes) -> float:
        import numpy as np
        scores = self._ensure().predict(np.frombuffer(frame, dtype=np.int16))
        return float(max(scores.values())) if scores else 0.0

    def triggered(self, frame: bytes) -> bool:
        return self.process(frame) >= self.threshold


class Segmenter:
    """Chops a 16kHz int16 PCM stream into utterances via VAD.

    Uses webrtcvad when available; otherwise an RMS energy gate. feed() accepts
    arbitrary-length frames, internally slicing to fixed frame_ms windows.
    Returns the utterance PCM when speech is followed by silence_ms of silence.
    """

    def __init__(self, rate: int = 16000, frame_ms: int = 20, silence_ms: int = 700,
                 aggressiveness: int = 2, energy_threshold: int = 500):
        self.rate = rate
        self.frame_bytes = int(rate * frame_ms / 1000) * 2  # 16-bit mono
        self.silence_frames = max(1, silence_ms // frame_ms)
        self.energy_threshold = energy_threshold
        self._buf = bytearray()
        self._utt = bytearray()
        self._in_speech = False
        self._silence_run = 0
        try:
            import webrtcvad
            self._vad = webrtcvad.Vad(aggressiveness)
        except Exception:  # noqa: BLE001 - missing/incompatible wheel -> energy fallback
            self._vad = None

    @property
    def in_speech(self) -> bool:
        return self._in_speech

    def _is_speech(self, fr: bytes) -> bool:
        if self._vad is not None:
            try:
                return self._vad.is_speech(fr, self.rate)
            except Exception:  # noqa: BLE001 - bad frame length etc. -> energy
                pass
        import audioop  # energy-VAD fallback; Python 3.13+ needs audioop-lts or pure-Python RMS (project targets 3.11/3.12)
        return audioop.rms(fr, 2) >= self.energy_threshold

    def feed(self, frame: bytes):
        self._buf.extend(frame)
        completed = None
        while len(self._buf) >= self.frame_bytes:
            fr = bytes(self._buf[:self.frame_bytes])
            del self._buf[:self.frame_bytes]
            if self._is_speech(fr):
                self._in_speech = True
                self._silence_run = 0
                self._utt.extend(fr)
            elif self._in_speech:
                self._utt.extend(fr)
                self._silence_run += 1
                if self._silence_run >= self.silence_frames:
                    completed = bytes(self._utt)
                    self._utt = bytearray()
                    self._in_speech = False
                    self._silence_run = 0
        return completed

    def reset(self) -> None:
        self._buf.clear()
        self._utt = bytearray()
        self._in_speech = False
        self._silence_run = 0
