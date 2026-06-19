#!/usr/bin/env python
"""Jarvis Web UI sidecar (Phase 5). Thin FastAPI glue over the Phase-1 router.

Wires the browser to the Jarvis brain without touching OpenJarvis/_vendor:
  GET  /api/health   -> liveness + router import check
  GET  /api/models   -> models for the Settings dropdown (+ per-task map)
  WS   /api/chat     -> streamed chat via jarvis_router (fallback ladder inside)
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))  # import sibling scripts

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import jarvis_router  # Phase-1 router (classify / build_ladder / complete_with_fallback)

app = FastAPI(title="Jarvis Web Sidecar", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "router_ok": hasattr(jarvis_router, "complete_with_fallback")}


@app.get("/api/models")
def models() -> dict:
    task_map = jarvis_router.task_model_map()
    # Distinct, non-empty model ids across the task map, plus the 'auto' router.
    distinct = [m for m in dict.fromkeys(task_map.values()) if m]
    return {"task_map": task_map, "models": ["auto", *distinct]}
