"""Phase 6 voice glue — STT (OpenJarvis faster-whisper) + TTS (Mark-XL EdgeTTS).

Pure reuse layer for the voice WS. Heavy libs are imported lazily so unit tests
run without them installed. No backbone/_vendor edits.
"""
from __future__ import annotations

import asyncio
import io
import os
import re
import sys
import wave
from pathlib import Path


def pcm_to_wav(pcm: bytes, rate: int = 16000, channels: int = 1, sampwidth: int = 2) -> bytes:
    """Wrap raw little-endian PCM in a canonical 44-byte WAV header."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sampwidth)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def split_sentences(text: str) -> list[str]:
    """Split text into sentences for streamed TTS (chunked by terminators)."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


_MARKXL = Path(__file__).resolve().parent.parent / "_vendor" / "Mark-XL"
_stt = None


def _get_stt():
    """Lazy-load a single FasterWhisperBackend (small/CPU/int8 by default)."""
    global _stt
    if _stt is None:
        from openjarvis.speech.faster_whisper import FasterWhisperBackend
        _stt = FasterWhisperBackend(
            model_size=os.environ.get("WHISPER_MODEL", "small"),
            device=os.environ.get("WHISPER_DEVICE", "cpu"),
            compute_type=os.environ.get("WHISPER_COMPUTE", "int8"),
        )
    return _stt


def transcribe(wav_bytes: bytes) -> str:
    """Transcribe WAV bytes via faster-whisper. Returns stripped text."""
    result = _get_stt().transcribe(wav_bytes, format="wav")
    return (result.text or "").strip()


def _edge_engine(voice: str):
    """Build a Mark-XL EdgeTTSEngine (adds _vendor/Mark-XL to sys.path once)."""
    if str(_MARKXL) not in sys.path:
        sys.path.insert(0, str(_MARKXL))
    from core.tts import EdgeTTSEngine
    return EdgeTTSEngine(voice=voice)


def synthesize(text: str, voice: str | None = None) -> bytes:
    """Synthesize mp3 bytes via Edge-TTS. BLOCKING — call via asyncio.to_thread.

    Uses EdgeTTSEngine._synth (returns bytes) rather than .speak() (which would
    play on the server's speakers). Runs its own event loop, so must NOT be
    awaited directly inside a running loop — wrap with asyncio.to_thread.
    """
    voice = voice or os.environ.get("TTS_VOICE", "en-US-GuyNeural")
    engine = _edge_engine(voice)
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(engine._synth(text))
    finally:
        loop.close()
