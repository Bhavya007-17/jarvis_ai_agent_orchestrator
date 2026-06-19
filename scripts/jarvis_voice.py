"""Phase 6 voice glue — STT (OpenJarvis faster-whisper) + TTS (Mark-XL EdgeTTS).

Pure reuse layer for the voice WS. Heavy libs are imported lazily so unit tests
run without them installed. No backbone/_vendor edits.
"""
from __future__ import annotations

import io
import os
import re
import wave


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
