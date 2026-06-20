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
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))  # import sibling scripts

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import jarvis_router  # Phase-1 router (classify / build_ladder / complete_with_fallback)
import jarvis_council  # Phase-4 multi-model planning council
import jarvis_memory   # Phase-3 personal_facts + session
import jarvis_voice    # Phase-6 STT/TTS glue
import jarvis_wake     # Phase-6 wake-word + VAD
from jarvis_memory import FactsStore
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
        # The Settings dropdown offers bare NIM ids (e.g. "meta/llama-3.3-70b"),
        # which contain "/" yet still need the LiteLLM "nvidia_nim/" provider
        # prefix.  Only ids already carrying a known provider prefix are left
        # as-is — otherwise the chosen rung 500s ("LLM Provider NOT provided")
        # and the user's selection is silently dropped to the fallback model.
        known = ("nvidia_nim/", "gemini/", "ollama/")
        full = model_choice if model_choice.startswith(known) \
            else f"{jarvis_router.NIM_PROVIDER}/{model_choice}"
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


async def speak_answer(send_json, send_bytes, answer, voice, cancel_event):
    """Synthesize the answer sentence-by-sentence and stream mp3 to the client.
    Honors cancel_event (barge-in): stops between sentences and emits 'canceled'."""
    for i, sentence in enumerate(jarvis_voice.split_sentences(answer)):
        if cancel_event.is_set():
            await send_json({"type": "canceled"})
            return
        try:
            audio = await asyncio.to_thread(jarvis_voice.synthesize, sentence, voice)
        except Exception as exc:  # noqa: BLE001 - one bad sentence shouldn't kill the turn
            await send_json({"type": "error", "detail": f"tts: {exc}"})
            continue
        if cancel_event.is_set():
            await send_json({"type": "canceled"})
            return
        await send_json({"type": "speak_begin", "seq": i})
        await send_bytes(audio)
        await send_json({"type": "speak_end", "seq": i})


@app.websocket("/api/voice")
async def voice_ws(websocket: WebSocket) -> None:
    """Always-on wake-word voice loop (Phase 6). See spec §4 for the protocol."""
    await websocket.accept()
    # First client message should be the JSON config, but a mic frame can race
    # ahead of it (the audio worklet may flush the instant the socket opens).
    # Skip any leading binary frames until the text config arrives, rather than
    # crashing on receive_text() and dropping the socket — see voiceSocket.js.
    cfg: dict = {}
    try:
        while True:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                return
            if msg.get("text") is not None:
                try:
                    cfg = json.loads(msg["text"]) or {}
                except json.JSONDecodeError:
                    cfg = {}
                break
            # leading binary frame (pre-handshake audio) — ignore and keep waiting
    except (WebSocketDisconnect, RuntimeError):
        return
    model = (cfg or {}).get("model", "auto")
    voice = (cfg or {}).get("voice") or os.environ.get("TTS_VOICE", "en-US-GuyNeural")
    idle_timeout = float(os.environ.get("CONVO_IDLE_TIMEOUT", "20"))

    wake = jarvis_wake.WakeWord()
    seg = jarvis_wake.Segmenter()
    cancel_event = asyncio.Event()
    frame_q: asyncio.Queue = asyncio.Queue(maxsize=256)

    async def receiver():
        try:
            while True:
                msg = await websocket.receive()
                if msg.get("type") == "websocket.disconnect":
                    break
                if msg.get("bytes") is not None:
                    try:
                        frame_q.put_nowait(("audio", msg["bytes"]))
                    except asyncio.QueueFull:
                        try:
                            frame_q.get_nowait()  # drop oldest audio frame
                        except asyncio.QueueEmpty:
                            pass
                        frame_q.put_nowait(("audio", msg["bytes"]))
                elif msg.get("text") is not None:
                    try:
                        ctrl = json.loads(msg["text"])
                    except json.JSONDecodeError:
                        continue
                    if ctrl.get("type") == "cancel":
                        cancel_event.set()
        finally:
            await frame_q.put(("close", b""))  # sentinel must always get through

    recv_task = asyncio.create_task(receiver())
    loop = asyncio.get_running_loop()
    state = "sleeping"
    last_voice = loop.time()
    try:
        while True:
            try:
                kind, payload = await asyncio.wait_for(frame_q.get(), timeout=1.0)
            except asyncio.TimeoutError:
                if state == "active" and (loop.time() - last_voice) > idle_timeout:
                    state = "sleeping"
                    seg.reset()
                    await websocket.send_json({"type": "sleep"})
                continue
            if kind == "close":
                break
            if kind != "audio":
                continue
            frame = payload

            if state == "sleeping":
                if wake.triggered(frame):
                    state = "active"
                    seg.reset()
                    last_voice = loop.time()
                    await websocket.send_json({"type": "wake"})
                continue

            # active: segment into utterances
            utt = seg.feed(frame)
            if seg.in_speech:
                last_voice = loop.time()
            if utt is None:
                continue

            text = await asyncio.to_thread(jarvis_voice.transcribe, jarvis_voice.pcm_to_wav(utt))
            if not text.strip():
                continue
            await websocket.send_json({"type": "transcript", "text": text})
            last_voice = loop.time()

            cancel_event.clear()
            answer = ""
            async for fr in stream_chat(text, model):
                if fr["type"] == "chunk":
                    answer += fr.get("content", "")
                    await websocket.send_json(fr)
                elif fr["type"] == "rung":
                    await websocket.send_json(fr)
                elif fr["type"] == "done":
                    answer = fr.get("content", answer)
                elif fr["type"] == "error":
                    await websocket.send_json(fr)
            await websocket.send_json({"type": "answer", "content": answer})

            await speak_answer(websocket.send_json, websocket.send_bytes,
                               answer, voice, cancel_event)
            # Drain stale audio that buffered during the turn so the next
            # utterance starts fresh.  If a "close" sentinel is encountered
            # here it means the client disconnected during the turn — stop.
            _drain_found_close = False
            while not frame_q.empty():
                try:
                    _kind, _payload = frame_q.get_nowait()
                    if _kind == "close":
                        _drain_found_close = True
                        break
                except asyncio.QueueEmpty:
                    break
            seg.reset()
            await websocket.send_json({"type": "turn_end"})
            last_voice = loop.time()
            if _drain_found_close:
                break
    except WebSocketDisconnect:
        pass
    finally:
        recv_task.cancel()


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


# ---------------------------------------------------------------------------
# Council (Phase 4) — stream the multi-model planning council live over WS.
# Voices run in a worker thread and emit frames into a thread-safe queue.
# ---------------------------------------------------------------------------
@app.websocket("/api/council")
async def council_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        data = json.loads(await websocket.receive_text())
    except json.JSONDecodeError:
        await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
        return
    except WebSocketDisconnect:
        return
    task = (data or {}).get("task", "").strip()
    if not task:
        await websocket.send_json({"type": "error", "detail": "Missing 'task'"})
        return
    execute = bool((data or {}).get("execute", False))
    max_tokens = int((data or {}).get("max_tokens", 400))

    # Council voices each spin a nested asyncio.run internally, so we bridge with
    # a plain thread-safe queue (no cross-loop call_soon_threadsafe, which drops
    # frames emitted from inside the nested loop). The WS coroutine blocks on
    # queue.get in the default executor so the event loop stays free.
    import queue as _queue
    import threading

    q: "_queue.Queue" = _queue.Queue()
    sentinel = object()

    def emit(frame: dict) -> None:
        q.put(frame)

    def run() -> None:
        try:
            jarvis_council.run_council(task, stream=True, execute=execute,
                                       max_tokens=max_tokens, emit=emit)
        except Exception as exc:  # noqa: BLE001 - surface council failure as a frame
            q.put({"type": "error", "detail": str(exc)})
        finally:
            q.put(sentinel)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    try:
        while True:
            frame = await asyncio.to_thread(q.get)
            if frame is sentinel:
                break
            await websocket.send_json(frame)
    except WebSocketDisconnect:
        pass


# ---------------------------------------------------------------------------
# Memory (Phase 3) — personal_facts CRUD + session, via jarvis_memory.
# ---------------------------------------------------------------------------
@app.get("/api/memory/facts")
def memory_facts() -> dict:
    return {"facts": FactsStore().load(), "categories": list(jarvis_memory.VALID_CATEGORIES)}


@app.post("/api/memory/facts")
async def memory_remember(payload: dict) -> dict:
    key = (payload or {}).get("key", "").strip()
    value = (payload or {}).get("value", "").strip()
    category = (payload or {}).get("category", "notes")
    if not key or not value:
        return {"ok": False, "message": "key and value are required"}
    msg = FactsStore().remember(key, value, category)
    return {"ok": True, "message": msg, "facts": FactsStore().load()}


@app.delete("/api/memory/facts")
def memory_forget(key: str, category: str = "notes") -> dict:
    msg = FactsStore().forget(key, category)
    return {"ok": True, "message": msg, "facts": FactsStore().load()}


@app.get("/api/memory/session")
def memory_session(user: str = "default", limit: int = 10) -> dict:
    return {"text": jarvis_memory.show_session(user, limit)}


# ---------------------------------------------------------------------------
# Routing map (Phase 1) — task->model map + ladders for the Graph tab.
# ---------------------------------------------------------------------------
@app.get("/api/routing")
def routing() -> dict:
    ladders = {tt: [{"label": l, "model": m} for l, m in jarvis_router.build_ladder(tt)]
               for tt in ("reasoning", "code", "general")}
    return {"task_map": jarvis_router.task_model_map(), "ladders": ladders,
            "graph_url": os.environ.get("CBM_GRAPH_URL", "http://localhost:9749")}


# ---------------------------------------------------------------------------
# Tools / MCP (Phase 2) — list configured servers, add one, discover tools.
# ---------------------------------------------------------------------------
def _config_path():
    from openjarvis.core.paths import get_config_dir
    return get_config_dir() / "config.toml"


def _load_mcp_servers() -> list:
    import tomllib
    p = _config_path()
    if not p.exists():
        return []
    try:
        cfg = tomllib.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - malformed config -> empty list
        return []
    raw = cfg.get("tools", {}).get("mcp", {}).get("servers", "[]")
    try:
        return json.loads(raw) if isinstance(raw, str) else (raw or [])
    except json.JSONDecodeError:
        return []


def _write_mcp_servers(servers: list) -> None:
    import re
    p = _config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    line = f"servers = '{json.dumps(servers)}'"
    text = p.read_text(encoding="utf-8") if p.exists() else ""
    if "[tools.mcp]" in text and re.search(r"servers = '[^']*'", text):
        text = re.sub(r"servers = '[^']*'", lambda _m: line, text)  # literal repl (keeps backslashes)
    else:
        new_section = "\n\n[tools.mcp]\nenabled = true\n" + line + "\n"
        text = (text.rstrip() + new_section).lstrip()
    p.write_text(text, encoding="utf-8")


_MCP_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_BLOCKED_COMMANDS = {"sh", "bash", "zsh", "cmd", "cmd.exe", "powershell",
                     "powershell.exe", "pwsh", "pwsh.exe"}


def _validate_mcp_server(name: str, command: str, args: list) -> str | None:
    """Reject registrations that could turn the (subprocess-spawning) MCP
    loader into an RCE vector. Returns an error message, or None if valid."""
    if not _MCP_NAME_RE.match(name):
        return "name must be 1-64 chars of letters, digits, dot, dash, underscore"
    if "'" in name or "'" in command:
        return "single quotes are not allowed"
    base = os.path.basename(command).lower()
    if base in _BLOCKED_COMMANDS:
        return f"command '{base}' is blocked (no shell interpreters)"
    for a in args:
        if not isinstance(a, str):
            return "args must all be strings"
        if "'" in a:
            return "single quotes are not allowed in args"
    return None


@app.get("/api/mcp/servers")
def mcp_servers() -> dict:
    return {"servers": _load_mcp_servers()}


@app.post("/api/mcp/servers")
async def mcp_add_server(payload: dict) -> dict:
    name = (payload or {}).get("name", "").strip()
    command = (payload or {}).get("command", "").strip()
    args = (payload or {}).get("args", [])
    if not name or not command:
        return {"ok": False, "message": "name and command are required"}
    if not isinstance(args, list):
        args = [str(args)]
    err = _validate_mcp_server(name, command, args)
    if err:
        return {"ok": False, "message": err}
    servers = [s for s in _load_mcp_servers() if s.get("name") != name]
    servers.append({"name": name, "command": command, "args": args})
    _write_mcp_servers(servers)
    return {"ok": True, "message": f"Added MCP server '{name}'", "servers": servers}


@app.get("/api/mcp/tools")
def mcp_tools() -> dict:
    try:
        from openjarvis.core.config import load_config
        from openjarvis.mcp.loader import load_mcp_tools_from_config
        cfg = load_config()
        tools, clients = load_mcp_tools_from_config(cfg.tools.mcp)
        try:
            names = sorted(t.spec.name for t in tools)
        finally:
            for c in clients:
                try:
                    c.close()
                except Exception:  # noqa: BLE001
                    pass
        return {"ok": True, "tools": names}
    except Exception as exc:  # noqa: BLE001 - discovery is best-effort (spawns servers)
        return {"ok": False, "tools": [], "detail": str(exc)}
