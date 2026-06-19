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
