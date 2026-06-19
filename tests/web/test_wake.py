import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import jarvis_wake


class _FakeModel:
    def __init__(self, score): self._score = score
    def predict(self, audio): return {"hey_jarvis": self._score}


def test_wakeword_triggers_above_threshold(monkeypatch):
    w = jarvis_wake.WakeWord(threshold=0.5)
    monkeypatch.setattr(w, "_ensure", lambda: _FakeModel(0.9))
    frame = b"\x00\x01" * 640
    assert w.process(frame) == 0.9
    assert w.triggered(frame) is True


def test_wakeword_silent_below_threshold(monkeypatch):
    w = jarvis_wake.WakeWord(threshold=0.5)
    monkeypatch.setattr(w, "_ensure", lambda: _FakeModel(0.1))
    assert w.triggered(b"\x00\x00" * 640) is False
