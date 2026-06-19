import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import jarvis_voice


def test_pcm_to_wav_has_riff_wave_header():
    pcm = b"\x01\x00" * 160  # 10ms of 16kHz 16-bit silence-ish
    wav = jarvis_voice.pcm_to_wav(pcm)
    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"
    assert len(wav) == 44 + len(pcm)  # 44-byte canonical header + data


def test_split_sentences_splits_on_terminators():
    assert jarvis_voice.split_sentences("Hi there. How are you?") == ["Hi there.", "How are you?"]
    assert jarvis_voice.split_sentences("  ") == []
    assert jarvis_voice.split_sentences("No terminator") == ["No terminator"]


class _FakeResult:
    def __init__(self, text): self.text = text

class _FakeSTT:
    def transcribe(self, wav, *, format="wav", language=None):
        assert format == "wav"
        return _FakeResult("  hello jarvis  ")

def test_transcribe_returns_stripped_text(monkeypatch):
    monkeypatch.setattr(jarvis_voice, "_get_stt", lambda: _FakeSTT())
    assert jarvis_voice.transcribe(b"RIFF....") == "hello jarvis"

class _FakeEdge:
    def __init__(self, voice): self.voice = voice
    async def _synth(self, text): return b"MP3:" + text.encode()

def test_synthesize_returns_mp3_bytes(monkeypatch):
    monkeypatch.setattr(jarvis_voice, "_edge_engine", lambda voice: _FakeEdge(voice))
    out = jarvis_voice.synthesize("hi", voice="v")
    assert out == b"MP3:hi"


import asyncio as _asyncio
import jarvis_web_api

def _run(coro): return _asyncio.new_event_loop().run_until_complete(coro)

class _Sink:
    def __init__(self): self.frames = []; self.audio = []
    async def send_json(self, f): self.frames.append(f)
    async def send_bytes(self, b): self.audio.append(b)

def test_speak_answer_streams_each_sentence(monkeypatch):
    monkeypatch.setattr(jarvis_voice, "synthesize", lambda s, v: b"MP3:" + s.encode())
    s = _Sink()
    ev = _asyncio.Event()
    _run(jarvis_web_api.speak_answer(s.send_json, s.send_bytes, "Hi. Bye.", "v", ev))
    assert [f["type"] for f in s.frames] == ["speak_begin", "speak_end", "speak_begin", "speak_end"]
    assert s.audio == [b"MP3:Hi.", b"MP3:Bye."]

def test_speak_answer_cancels_before_first_sentence(monkeypatch):
    monkeypatch.setattr(jarvis_voice, "synthesize", lambda s, v: b"MP3")
    s = _Sink()
    ev = _asyncio.Event(); ev.set()
    _run(jarvis_web_api.speak_answer(s.send_json, s.send_bytes, "Hi. Bye.", "v", ev))
    assert s.frames == [{"type": "canceled"}]
    assert s.audio == []
