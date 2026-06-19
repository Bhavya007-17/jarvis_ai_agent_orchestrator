#!/usr/bin/env python
"""Jarvis Web UI sidecar (Phase 5). Thin FastAPI glue over the Phase-1 router.

Wires the browser to the Jarvis brain without touching OpenJarvis/_vendor:
  GET  /api/health   -> liveness + router import check
  GET  /api/models   -> models for the Settings dropdown (+ per-task map)
  WS   /api/chat     -> streamed chat via jarvis_router (fallback ladder inside)
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))  # import sibling scripts

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import jarvis_router  # Phase-1 router (classify / build_ladder / complete_with_fallback)
from openjarvis.core.types import Message, Role
from openjarvis.engine.litellm import LiteLLMEngine

app = FastAPI(title="Jarvis Web Sidecar", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_SYSTEM = "You are Jarvis. Be concise and helpful."


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "router_ok": hasattr(jarvis_router, "complete_with_fallback")}


@app.get("/api/models")
def models() -> dict:
    task_map = jarvis_router.task_model_map()
    # Distinct, non-empty model ids across the task map, plus the 'auto' router.
    distinct = [m for m in dict.fromkeys(task_map.values()) if m]
    return {"task_map": task_map, "models": ["auto", *distinct]}


def _ladder_for(message: str, model_choice: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (task_type, ladder). 'auto' routes by task; a concrete model id
    leads its own rung, then the normal fallback rungs (deduped)."""
    task_type = jarvis_router.classify(message)
    base = jarvis_router.build_ladder(task_type)
    if model_choice and model_choice != "auto":
        full = model_choice if "/" in model_choice else f"{jarvis_router.NIM_PROVIDER}/{model_choice}"
        rest = [r for r in base if r[1] != full]
        return task_type, [("chosen", full), *rest]
    return task_type, base


async def stream_chat(message: str, model_choice: str, max_tokens: int = 512):
    """Yield chat frames. Stream the top rung; on any stream error fall back to
    the laddered synchronous call (inherits Phase-1 backoff + NIM->Gemini->local)."""
    task_type, ladder = _ladder_for(message, model_choice)
    messages = [Message(role=Role.SYSTEM, content=_SYSTEM),
                Message(role=Role.USER, content=message)]

    if ladder:
        label, model = ladder[0]
        full = ""
        try:
            yield {"type": "rung", "rung": label, "model": model}
            async for piece in LiteLLMEngine().stream(messages, model=model, max_tokens=max_tokens):
                full += piece
                yield {"type": "chunk", "content": piece}
            if full.strip():
                yield {"type": "done", "content": full}
                return
        except Exception:  # noqa: BLE001 - any stream error -> laddered sync
            pass

    try:
        result = await asyncio.to_thread(
            jarvis_router.complete_with_fallback,
            messages, task_type, max_tokens=max_tokens, ladder=ladder or None,
        )
        yield {"type": "rung", "rung": result["rung"], "model": result["model"]}
        yield {"type": "chunk", "content": result["content"]}
        yield {"type": "done", "content": result["content"]}
    except Exception as exc:  # noqa: BLE001 - every rung failed
        yield {"type": "error", "detail": str(exc)}


@app.websocket("/api/chat")
async def chat_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            try:
                data = json.loads(await websocket.receive_text())
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
                continue
            message = (data or {}).get("message", "").strip()
            if not message:
                await websocket.send_json({"type": "error", "detail": "Missing 'message'"})
                continue
            model_choice = (data or {}).get("model", "auto")
            async for frame in stream_chat(message, model_choice):
                await websocket.send_json(frame)
    except WebSocketDisconnect:
        return
