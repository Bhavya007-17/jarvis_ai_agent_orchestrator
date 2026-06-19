import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import jarvis_wake
import struct


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


def _frame(amplitude, samples=320):
    return struct.pack("<%dh" % samples, *([amplitude] * samples))  # 20ms @16k


def test_segmenter_emits_utterance_after_trailing_silence(monkeypatch):
    seg = jarvis_wake.Segmenter(frame_ms=20, silence_ms=40)  # 2 silence frames ends it
    seg._vad = None  # force energy path (deterministic)
    loud = _frame(20000)
    quiet = _frame(0)
    assert seg.feed(loud) is None        # speech starts
    assert seg.in_speech is True
    assert seg.feed(loud) is None        # still speaking
    assert seg.feed(quiet) is None       # 1st silence
    utt = seg.feed(quiet)                # 2nd silence -> end of utterance
    assert utt is not None
    assert len(utt) == 4 * 640           # 4 frames * 640 bytes (320 samples*2)
    assert seg.in_speech is False


def test_segmenter_ignores_leading_silence():
    seg = jarvis_wake.Segmenter(frame_ms=20, silence_ms=40)
    seg._vad = None
    assert seg.feed(_frame(0)) is None
    assert seg.in_speech is False
