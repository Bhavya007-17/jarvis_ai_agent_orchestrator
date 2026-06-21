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
