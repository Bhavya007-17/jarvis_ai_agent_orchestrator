#!/usr/bin/env python
"""Jarvis agent graph (Phase 9) — topological multi-agent execution.

A generalization of the Phase-4 council: instead of a fixed
propose->critique->synthesize pipeline, the user draws a DAG of agents and the
graph runs in topological order. Each node's prompt is the task plus the
concatenated outputs of its upstream (incoming-edge) nodes; the terminal
``orchestrator`` node synthesizes everything that flows into it.

Reuses (never re-implements): jarvis_council's streaming (`_astream`), ladder
(`_ladder_from`/`_nim`), synthesis policy (`synthesis_directive`), reasoning
switch (`THINKING_ON`), and the Phase-1 router fallback. The only new logic is
the async, concurrency-bounded DAG scheduler.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # sibling-script imports

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:  # noqa: BLE001
    pass

import jarvis_council  # noqa: E402
from jarvis_council import (  # noqa: E402
    THINKING_ON,
    _general_model,
    _ladder_from,
    _nim,
    _reasoning_model,
    synthesis_directive,
)
from jarvis_router import complete_with_fallback  # noqa: E402
from openjarvis.core.types import Message, Role  # noqa: E402
from openjarvis.engine.litellm import LiteLLMEngine  # noqa: E402

ORCH_ID = "orchestrator"
MAX_NODES = 16
CONCURRENCY = 3


def _adjacency(nodes: list[dict], edges: list[dict]):
    ids = {n["id"] for n in nodes}
    preds = {nid: set() for nid in ids}
    succs = {nid: set() for nid in ids}
    for e in edges:
        s, t = e["source"], e["target"]
        if s in ids and t in ids:
            succs[s].add(t)
            preds[t].add(s)
    return preds, succs


def _has_cycle(nodes: list[dict], edges: list[dict]) -> bool:
    preds, succs = _adjacency(nodes, edges)
    indeg = {nid: len(preds[nid]) for nid in preds}
    ready = [nid for nid, d in indeg.items() if d == 0]
    seen = 0
    while ready:
        n = ready.pop()
        seen += 1
        for m in succs[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                ready.append(m)
    return seen != len(indeg)


def _reaches_orchestrator(nodes: list[dict], edges: list[dict]) -> set[str]:
    """Set of node ids that have a directed path to the orchestrator."""
    preds, _ = _adjacency(nodes, edges)
    stack, reach = [ORCH_ID], set()
    while stack:
        n = stack.pop()
        if n in reach:
            continue
        reach.add(n)
        stack.extend(preds.get(n, ()))
    return reach


def _ordered(ids, nodes: list[dict]) -> list[str]:
    order = {n["id"]: i for i, n in enumerate(nodes)}
    return sorted(ids, key=lambda x: order.get(x, 1_000_000))


def _validate_graph(graph: dict) -> str | None:
    """Return an error string, or None if the graph is a well-formed DAG that
    terminates at the orchestrator and references only .env-derived models."""
    if not isinstance(graph, dict):
        return "graph must be an object"
    task = str(graph.get("task", "")).strip()
    if not task:
        return "task is required"
    nodes = graph.get("nodes")
    edges = graph.get("edges", [])
    if not isinstance(nodes, list) or not nodes:
        return "nodes must be a non-empty list"
    if not isinstance(edges, list):
        return "edges must be a list"
    if len(nodes) > MAX_NODES:
        return f"too many nodes (max {MAX_NODES})"

    known = jarvis_council._known_models()
    ids: set[str] = set()
    agent_count = 0
    has_orch = False
    for n in nodes:
        if not isinstance(n, dict):
            return "each node must be an object"
        nid = str(n.get("id", "")).strip()
        if not nid:
            return "each node needs an 'id'"
        if nid in ids:
            return f"duplicate node id {nid!r}"
        ids.add(nid)
        if not str(n.get("persona", "")).strip():
            return f"node {nid!r} needs a 'persona'"
        if nid == ORCH_ID:
            has_orch = True
        else:
            agent_count += 1
            model = str(n.get("model", "")).strip()
            if not model:
                return f"node {nid!r} needs a 'model'"
            if model not in known:
                return f"unknown model {model!r}; not in the .env model set"
    if not has_orch:
        return "graph must include the 'orchestrator' node"
    if agent_count == 0:
        return "graph needs at least one agent node"

    for e in edges:
        if not isinstance(e, dict):
            return "each edge must be an object"
        s = str(e.get("source", "")).strip()
        t = str(e.get("target", "")).strip()
        if not s or not t:
            return "each edge needs 'source' and 'target'"
        if s not in ids or t not in ids:
            return "edge references unknown node id"
        if s == ORCH_ID:
            return "orchestrator must be a terminal sink (no outgoing edges)"

    if _has_cycle(nodes, edges):
        return "graph has a cycle (must be a DAG)"
    reach = _reaches_orchestrator(nodes, edges)
    for n in nodes:
        if n["id"] != ORCH_ID and n["id"] not in reach:
            return f"node {n['id']!r} has no path to the orchestrator"
    return None


# ---------------------------------------------------------------------------
# Execution — async, topological, concurrency-bounded (<=3 LLM calls in flight).
# ---------------------------------------------------------------------------


def _node_prompt(node: dict, task: str, upstream: list[tuple[str, str]], is_orch: bool):
    """Build (system, user, ladder, extra_body) for one node."""
    if is_orch:
        directive = synthesis_directive(
            [{"persona": p, "content": c} for p, c in upstream], "")
        system = ("You are the council orchestrator. " + directive +
                  " Produce ONE final plan as a numbered list of concrete steps.")
        body = "\n\n".join(f"### From {p}\n{c}" for p, c in upstream)
        user = f"Task: {task}\n\n{body}" if body else f"Task: {task}"
        model_id = _reasoning_model() or _general_model()
        return system, user, _ladder_from(_nim(model_id)), THINKING_ON
    system = node.get("lens", "") or f"You are {node.get('persona', 'an agent')}."
    body = "\n\n".join(f"### From {p}\n{c}" for p, c in upstream)
    user = task if not body else f"{task}\n\nUpstream analysis to build on:\n{body}"
    return system, user, _ladder_from(_nim(node["model"])), None


async def _default_call_node(node, system, user, ladder, *, max_tokens, extra_body, emit):
    """Stream the primary rung live; on any failure walk the laddered, backed-off
    `complete_with_fallback`. Reuses jarvis_council._astream (adapting its
    voice_chunk frame into a node_chunk frame keyed by this node's id)."""
    nid = node["id"]
    msgs = [Message(role=Role.SYSTEM, content=system),
            Message(role=Role.USER, content=user)]
    primary = ladder[0][1]
    chunk_emit = None
    if emit:
        def chunk_emit(frame):  # noqa: E306 - tiny adapter
            emit({"type": "node_chunk", "node": nid, "content": frame.get("content", "")})
    try:
        text = await jarvis_council._astream(
            LiteLLMEngine(), msgs, primary, max_tokens, extra_body,
            emit=chunk_emit, label=nid)
        if text.strip():
            return {"content": text, "model": primary}
    except Exception:  # noqa: BLE001 - any stream error => ladder
        pass
    res = await asyncio.to_thread(
        complete_with_fallback, msgs, "general",
        max_tokens=max_tokens, extra_body=extra_body, ladder=ladder)
    if emit:
        emit({"type": "node_chunk", "node": nid, "content": res["content"]})
    return {"content": res["content"], "model": res["model"]}


async def run_graph(graph: dict, *, emit=None, max_tokens: int = 400,
                    call_node=None) -> dict:
    """Execute the agent DAG in topological order with <=3 concurrent LLM calls."""
    err = _validate_graph(graph)
    if err:
        if emit:
            emit({"type": "error", "detail": err})
        return {"output": "", "outputs": {}, "models": {}, "error": err}

    if call_node is None:
        call_node = _default_call_node
    task = graph["task"].strip()
    nodes = graph["nodes"]
    edges = graph.get("edges", [])
    by_id = {n["id"]: n for n in nodes}
    preds, succs = _adjacency(nodes, edges)
    sem = asyncio.Semaphore(CONCURRENCY)
    outputs: dict[str, str] = {}
    models: dict[str, str] = {}
    node_tasks: dict[str, asyncio.Task] = {}

    async def run_one(nid: str) -> str:
        if preds[nid]:
            await asyncio.gather(*(node_tasks[p] for p in preds[nid]))
        node = by_id[nid]
        is_orch = nid == ORCH_ID
        upstream = [(by_id[p].get("persona", p), outputs.get(p, ""))
                    for p in _ordered(preds[nid], nodes)]
        system, user, ladder, extra_body = _node_prompt(node, task, upstream, is_orch)
        async with sem:
            if emit:
                emit({"type": "node_start", "node": nid})
            res = await call_node(node, system, user, ladder,
                                  max_tokens=max_tokens + (200 if is_orch else 0),
                                  extra_body=extra_body, emit=emit)
        text = res.get("content", "")
        outputs[nid] = text
        models[nid] = res.get("model", ladder[0][1])
        if emit:
            emit({"type": "node_end", "node": nid, "content": text, "model": models[nid]})
            for tgt in _ordered(succs[nid], nodes):
                emit({"type": "edge_flow", "source": nid, "target": tgt})
        return text

    for nid in by_id:
        node_tasks[nid] = asyncio.create_task(run_one(nid))
    await asyncio.gather(*node_tasks.values())

    output = outputs.get(ORCH_ID, "")
    if emit:
        emit({"type": "graph_done", "output": output})
    return {"output": output, "outputs": outputs, "models": models}
