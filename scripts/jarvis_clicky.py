#!/usr/bin/env python
"""Jarvis Clicky — screen-aware Q&A + on-screen pointing (Phase 11 / slice F).

"Where is X on my screen?" -> capture the host screen, a vision model locates the
element via **two-stage grid (Set-of-Mark) prompting**, and the result is an
annotated screenshot with the spot highlighted plus a short answer.

Ports the model-agnostic locator from
``_vendor/clicky-windows/ai/universal_locator.py`` (grid draw + cell parse +
two-stage mapping) and the mss capture from
``_vendor/Mark-XL/actions/screen_processor.py``. The async streaming-provider
seam is replaced by a sync ``_vision_ask`` that rides OpenJarvis's
``LiteLLMEngine`` (no new LLM path), targeting the vision model named by
``.env`` ``VISION_MODEL`` (never hardcoded).

CLI:  uv run python scripts/jarvis_clicky.py "where is the Save button"
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

# The script dir must be importable so `jarvis_router` resolves when run
# directly; importing it also loads .env and mirrors NVIDIA_API_KEY ->
# NVIDIA_NIM_API_KEY for the engine.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import jarvis_router  # noqa: E402,F401  (import side effect: .env + key mirror)
from openjarvis.core.types import Message, Role  # noqa: E402
from openjarvis.engine.litellm import LiteLLMEngine  # noqa: E402

# ── Tunables (from clicky universal_locator) ────────────────────────────────
STAGE1_COLS, STAGE1_ROWS = 12, 8
STAGE2_COLS, STAGE2_ROWS = 6, 6
ZOOM_RADIUS_CELLS = 1            # 3x3 region around the Stage-1 pick
MAX_INFERENCE_WIDTH = 1280

_KNOWN_PREFIXES = (
    "nvidia_nim/", "openai/", "anthropic/", "groq/", "openrouter/",
    "mistral/", "gemini/", "google/", "ollama/", "azure/",
)

_SYS = (
    "You are a precise UI element locator. You ALWAYS answer with a single JSON "
    'object of the form {"cell": <integer>}.'
)


# ── Engine / model resolution ───────────────────────────────────────────────
def _engine() -> LiteLLMEngine:  # seam for tests
    return LiteLLMEngine()


def _resolve_model() -> str | None:
    """Vision model id from .env VISION_MODEL, prefixed nvidia_nim/ if bare."""
    m = os.environ.get("VISION_MODEL", "").strip()
    if not m:
        return None
    if any(m.startswith(p) for p in _KNOWN_PREFIXES):
        return m
    return f"nvidia_nim/{m}"


def _vision_ask(prompt: str, image_b64: str, model: str) -> str:
    """One vision completion through LiteLLMEngine (OpenAI image blocks)."""
    content = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
    ]
    messages = [
        Message(role=Role.SYSTEM, content=_SYS),
        Message(role=Role.USER, content=content),
    ]
    try:
        result = _engine().generate(messages, model=model, max_tokens=120, temperature=0.0)
        return (result.get("content") or "").strip()
    except Exception:
        return ""


# ── Grid drawing + geometry (ported) ────────────────────────────────────────
def _load_font(size: int):
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_grid(img: Image.Image, cols: int, rows: int) -> Image.Image:
    """Overlay a red numbered grid (1..cols*rows, row-major). Returns RGB."""
    base = img.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = base.size
    cell_w, cell_h = w / cols, h / rows

    for c in range(1, cols):
        x = int(c * cell_w)
        draw.line([(x, 0), (x, h)], fill=(255, 0, 0, 200), width=1)
    for r in range(1, rows):
        y = int(r * cell_h)
        draw.line([(0, y), (w, y)], fill=(255, 0, 0, 200), width=1)

    font_size = max(12, min(28, int(min(cell_w, cell_h) / 3.5)))
    font = _load_font(font_size)
    n = 1
    for r in range(rows):
        for c in range(cols):
            cx, cy = int(c * cell_w) + 2, int(r * cell_h) + 2
            label = str(n)
            try:
                bbox = draw.textbbox((cx, cy), label, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            except Exception:
                tw, th = font_size * len(label) // 2, font_size
            draw.rectangle([(cx - 1, cy - 1), (cx + tw + 4, cy + th + 4)], fill=(255, 0, 0, 220))
            draw.text((cx + 2, cy), label, fill=(255, 255, 255, 255), font=font)
            n += 1

    return Image.alpha_composite(base, overlay).convert("RGB")


def _cell_center(pick: int, cols: int, rows: int, w: int, h: int) -> tuple[int, int]:
    idx = pick - 1
    row, col = idx // cols, idx % cols
    x = int((col + 0.5) * w / cols)
    y = int((row + 0.5) * h / rows)
    return x, y


_PARSE_RE = re.compile(r"\b(\d{1,3})\b")


def _parse_cell_number(text: str, max_n: int) -> int | None:
    """Extract a cell 1..max_n from a free-form reply; JSON first, then ints."""
    m = re.search(r"\{[^{}]*\}", text or "", flags=re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            for key in ("cell", "number", "n", "answer"):
                if key in obj:
                    n = int(obj[key])
                    if 1 <= n <= max_n:
                        return n
        except Exception:
            pass
    for tok in _PARSE_RE.findall(text or ""):
        try:
            n = int(tok)
            if 1 <= n <= max_n:
                return n
        except ValueError:
            continue
    return None


def _img_to_b64(img: Image.Image, quality: int = 85) -> str:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _b64_to_img(b64: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")


def _grid_prompt(question: str, max_n: int) -> str:
    return (
        f"You are looking at a screenshot with a red numbered grid overlay. "
        f"Cells are numbered 1 to {max_n}, left-to-right, top-to-bottom.\n\n"
        f'The user asked: "{question}"\n\n'
        f"Identify the SINGLE numbered cell that most precisely contains the UI "
        f"element the user is asking about (button, link, menu item, icon, text "
        f"field, etc.).\n\n"
        f'Respond with ONLY this JSON, nothing else:  {{"cell": <number>}}\n\n'
        f'If there is no specific UI element to point at, respond:  {{"cell": 0}}'
    )


def _ask_grid(ask, img: Image.Image, question: str, cols: int, rows: int, model: str) -> int | None:
    max_n = cols * rows
    reply = ask(_grid_prompt(question, max_n), _img_to_b64(_draw_grid(img, cols, rows)), model)
    return _parse_cell_number(reply, max_n)


# ── Locate (two-stage) ──────────────────────────────────────────────────────
def locate(screenshot_b64: str, width: int, height: int, question: str,
           model: str | None = None, ask=None) -> tuple[int, int] | None:
    """Two-stage grid pointing. Returns (x, y) in the screenshot's pixel space,
    or None if the model picks no cell (conceptual question)."""
    ask = ask or _vision_ask
    img = _b64_to_img(screenshot_b64)

    s1 = _ask_grid(ask, img, question, STAGE1_COLS, STAGE1_ROWS, model)
    if s1 is None:
        return None

    idx = s1 - 1
    s1_row, s1_col = idx // STAGE1_COLS, idx % STAGE1_COLS
    cell_w, cell_h = width / STAGE1_COLS, height / STAGE1_ROWS

    c0 = max(0, s1_col - ZOOM_RADIUS_CELLS)
    r0 = max(0, s1_row - ZOOM_RADIUS_CELLS)
    c1 = min(STAGE1_COLS - 1, s1_col + ZOOM_RADIUS_CELLS)
    r1 = min(STAGE1_ROWS - 1, s1_row + ZOOM_RADIUS_CELLS)
    crop_left, crop_top = int(c0 * cell_w), int(r0 * cell_h)
    crop_right, crop_bottom = int((c1 + 1) * cell_w), int((r1 + 1) * cell_h)
    crop = img.crop((crop_left, crop_top, crop_right, crop_bottom))

    s2 = _ask_grid(ask, crop, question, STAGE2_COLS, STAGE2_ROWS, model)
    if s2 is None:
        return _cell_center(s1, STAGE1_COLS, STAGE1_ROWS, width, height)

    s2_idx = s2 - 1
    s2_row, s2_col = s2_idx // STAGE2_COLS, s2_idx % STAGE2_COLS
    s2_cw = (crop_right - crop_left) / STAGE2_COLS
    s2_ch = (crop_bottom - crop_top) / STAGE2_ROWS
    x = int(crop_left + (s2_col + 0.5) * s2_cw)
    y = int(crop_top + (s2_row + 0.5) * s2_ch)
    return x, y


def annotate(screenshot_b64: str, x: int, y: int) -> str:
    """Draw a highlight marker at (x, y); return the annotated JPEG b64."""
    base = _b64_to_img(screenshot_b64).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for radius, alpha in ((34, 90), (22, 150), (10, 230)):
        draw.ellipse(
            [(x - radius, y - radius), (x + radius, y + radius)],
            outline=(0, 220, 255, alpha), width=3,
        )
    draw.line([(x - 14, y), (x + 14, y)], fill=(0, 220, 255, 255), width=2)
    draw.line([(x, y - 14), (x, y + 14)], fill=(0, 220, 255, 255), width=2)
    return _img_to_b64(Image.alpha_composite(base, overlay).convert("RGB"))


# ── Capture ─────────────────────────────────────────────────────────────────
def _capture_screen() -> tuple[str, int, int]:
    """Grab the primary monitor, downscale to <=MAX_INFERENCE_WIDTH, return b64+dims."""
    import mss

    with mss.mss() as sct:
        monitors = sct.monitors
        target = monitors[1] if len(monitors) > 1 else monitors[0]
        shot = sct.grab(target)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

    w, h = img.size
    if w > MAX_INFERENCE_WIDTH:
        scale = MAX_INFERENCE_WIDTH / w
        img = img.resize((MAX_INFERENCE_WIDTH, int(h * scale)), Image.Resampling.LANCZOS)
    return _img_to_b64(img), img.size[0], img.size[1]


# ── Orchestration ───────────────────────────────────────────────────────────
def point(question: str, model: str | None = None, capture=None, ask=None) -> dict:
    """Capture the screen, locate the element, return an annotated result.

    Returns {found, point:[x,y]|None, description, screenshot_b64}.
    """
    model = model or _resolve_model()
    if not model:
        return {
            "found": False,
            "point": None,
            "screenshot_b64": None,
            "description": (
                "Set VISION_MODEL in .env (e.g. a NIM vision model) to enable Clicky."
            ),
        }

    capture = capture or _capture_screen
    try:
        screenshot_b64, w, h = capture()
    except Exception as e:
        return {"found": False, "point": None, "screenshot_b64": None,
                "description": f"Screen capture failed: {e}"}

    pt = locate(screenshot_b64, w, h, question, model=model, ask=ask)
    if pt:
        return {
            "found": True,
            "point": [pt[0], pt[1]],
            "screenshot_b64": annotate(screenshot_b64, pt[0], pt[1]),
            "description": f'Here is where "{question}" points on screen.',
        }
    return {
        "found": False,
        "point": None,
        "screenshot_b64": screenshot_b64,
        "description": f'I couldn\'t find a specific element for "{question}" on screen.',
    }


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "What's on my screen?"
    res = point(q)
    res_print = {k: (v if k != "screenshot_b64" else f"<{len(v)} b64 chars>" if v else None)
                 for k, v in res.items()}
    print(json.dumps(res_print, indent=2))
