"""Phase 11 (Slice F) — Clicky screen-aware pointing.

The vision call (``ask``) and screen capture (``capture``) are injected, so
every test runs offline: no real screen, no model spend.
"""

import base64
import importlib
import io
import os
import sys

import pytest
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
cl = importlib.import_module("jarvis_clicky")


def _solid_b64(w=1200, h=800, color=(30, 30, 30)) -> str:
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


# --------------------------------------------------------------------------- #
# _parse_cell_number
# --------------------------------------------------------------------------- #
def test_parse_cell_json():
    assert cl._parse_cell_number('{"cell": 5}', 96) == 5


def test_parse_cell_integer_in_text():
    assert cl._parse_cell_number("I think it's cell 42 there", 96) == 42


def test_parse_cell_zero_means_none():
    assert cl._parse_cell_number('{"cell": 0}', 96) is None


def test_parse_cell_out_of_range_none():
    assert cl._parse_cell_number("999", 96) is None
    assert cl._parse_cell_number("no number here", 96) is None


# --------------------------------------------------------------------------- #
# grid drawing + geometry
# --------------------------------------------------------------------------- #
def test_draw_grid_preserves_size_and_mode():
    img = Image.new("RGB", (240, 160), (0, 0, 0))
    out = cl._draw_grid(img, 12, 8)
    assert out.size == (240, 160)
    assert out.mode == "RGB"


def test_cell_center_top_left():
    x, y = cl._cell_center(1, 12, 8, 1200, 800)
    assert (x, y) == (50, 50)


def test_cell_center_last_cell():
    x, y = cl._cell_center(96, 12, 8, 1200, 800)
    assert x == pytest.approx(1150, abs=1) and y == pytest.approx(750, abs=1)


# --------------------------------------------------------------------------- #
# locate — two-stage grid with an injected ask
# --------------------------------------------------------------------------- #
def test_locate_returns_point_in_bounds():
    b64 = _solid_b64(1200, 800)
    point = cl.locate(b64, 1200, 800, "the Save button", model="m", ask=lambda *a, **k: '{"cell": 1}')
    assert point is not None
    x, y = point
    assert 0 <= x <= 1200 and 0 <= y <= 800


def test_locate_conceptual_returns_none():
    b64 = _solid_b64()
    point = cl.locate(b64, 1200, 800, "what does HTML mean", model="m", ask=lambda *a, **k: '{"cell": 0}')
    assert point is None


def test_locate_uses_two_ask_calls():
    b64 = _solid_b64()
    calls = []

    def ask(prompt, image_b64, model=None):
        calls.append(1)
        return '{"cell": 3}'

    cl.locate(b64, 1200, 800, "x", model="m", ask=ask)
    assert len(calls) == 2  # stage 1 + stage 2


# --------------------------------------------------------------------------- #
# annotate
# --------------------------------------------------------------------------- #
def test_annotate_roundtrips_marked_image():
    b64 = _solid_b64(400, 300)
    out = cl.annotate(b64, 200, 150)
    assert isinstance(out, str) and len(out) > 0
    img = Image.open(io.BytesIO(base64.b64decode(out)))
    assert img.size == (400, 300)


# --------------------------------------------------------------------------- #
# point — orchestration with injected capture + ask
# --------------------------------------------------------------------------- #
def test_point_found():
    b64 = _solid_b64(1200, 800)
    out = cl.point(
        "where is the Save button",
        model="nvidia_nim/some-vlm",
        capture=lambda: (b64, 1200, 800),
        ask=lambda *a, **k: '{"cell": 5}',
    )
    assert out["found"] is True
    assert out["point"] and 0 <= out["point"][0] <= 1200
    assert out["screenshot_b64"]


def test_point_conceptual_not_found():
    b64 = _solid_b64()
    out = cl.point(
        "what is recursion",
        model="m",
        capture=lambda: (b64, 1200, 800),
        ask=lambda *a, **k: '{"cell": 0}',
    )
    assert out["found"] is False
    assert out["point"] is None
    assert out["screenshot_b64"]  # still returns the screenshot


def test_point_without_model_is_graceful(monkeypatch):
    monkeypatch.setattr(cl, "_resolve_model", lambda: None)
    out = cl.point("where is X", capture=lambda: (_solid_b64(), 1200, 800), ask=lambda *a, **k: "{}")
    assert out["found"] is False
    assert "VISION_MODEL" in out["description"]


# --------------------------------------------------------------------------- #
# _resolve_model — id from .env, prefixed
# --------------------------------------------------------------------------- #
def test_resolve_model_prefixes_bare_id(monkeypatch):
    monkeypatch.setenv("VISION_MODEL", "meta/llama-3.2-90b-vision-instruct")
    assert cl._resolve_model() == "nvidia_nim/meta/llama-3.2-90b-vision-instruct"


def test_resolve_model_keeps_provider_prefix(monkeypatch):
    monkeypatch.setenv("VISION_MODEL", "openai/gpt-4o")
    assert cl._resolve_model() == "openai/gpt-4o"


def test_resolve_model_unset_returns_none(monkeypatch):
    monkeypatch.delenv("VISION_MODEL", raising=False)
    assert cl._resolve_model() is None


# --------------------------------------------------------------------------- #
# _vision_ask builds multimodal content and degrades gracefully
# --------------------------------------------------------------------------- #
def test_vision_ask_builds_image_block(monkeypatch):
    captured = {}

    class _FakeEngine:
        def generate(self, messages, *, model, **kw):
            captured["model"] = model
            captured["messages"] = messages
            return {"content": "cell 7", "model": model}

    monkeypatch.setattr(cl, "_engine", lambda: _FakeEngine())
    out = cl._vision_ask("which cell?", _solid_b64(20, 20), "nvidia_nim/vlm")
    assert out == "cell 7"
    user_msg = captured["messages"][-1]
    # content carries an image_url block (OpenAI multimodal shape)
    types = {part["type"] for part in user_msg.content}
    assert "image_url" in types and "text" in types


def test_vision_ask_degrades_on_engine_error(monkeypatch):
    class _BoomEngine:
        def generate(self, *a, **k):
            raise RuntimeError("model down")

    monkeypatch.setattr(cl, "_engine", lambda: _BoomEngine())
    assert cl._vision_ask("q", _solid_b64(10, 10), "m") == ""
