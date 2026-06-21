import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import jarvis_graph as jg  # noqa: E402


# Two known .env model ids, monkeypatched so validation is deterministic offline.
KNOWN = {"meta/llama-3.3-70b", "qwen/qwen2.5-coder-32b"}


@pytest.fixture(autouse=True)
def _known(monkeypatch):
    monkeypatch.setattr(jg.jarvis_council, "_known_models", lambda: set(KNOWN))


def _orch():
    return {"id": "orchestrator", "persona": "Orchestrator"}


def _agent(i, model="meta/llama-3.3-70b"):
    return {"id": f"a{i}", "persona": f"Agent{i}", "lens": f"lens {i}", "model": model}


def _to_orch(*agent_ids):
    return [{"source": a, "target": "orchestrator"} for a in agent_ids]


def test_valid_flat_graph_passes():
    graph = {"task": "do x", "nodes": [_agent(1), _agent(2), _orch()],
             "edges": _to_orch("a1", "a2")}
    assert jg._validate_graph(graph) is None


def test_valid_chain_passes():
    # a1,a2 -> a3 -> orchestrator
    graph = {"task": "t", "nodes": [_agent(1), _agent(2), _agent(3), _orch()],
             "edges": [{"source": "a1", "target": "a3"},
                       {"source": "a2", "target": "a3"},
                       {"source": "a3", "target": "orchestrator"}]}
    assert jg._validate_graph(graph) is None


def test_missing_task_rejected():
    graph = {"task": "  ", "nodes": [_agent(1), _orch()], "edges": _to_orch("a1")}
    assert "task" in jg._validate_graph(graph)


def test_empty_nodes_rejected():
    assert jg._validate_graph({"task": "t", "nodes": [], "edges": []})


def test_duplicate_id_rejected():
    graph = {"task": "t", "nodes": [_agent(1), _agent(1), _orch()], "edges": _to_orch("a1")}
    assert "duplicate" in jg._validate_graph(graph)


def test_unknown_model_rejected():
    graph = {"task": "t", "nodes": [_agent(1, model="evil/model"), _orch()],
             "edges": _to_orch("a1")}
    assert "unknown model" in jg._validate_graph(graph)


def test_edge_to_unknown_node_rejected():
    graph = {"task": "t", "nodes": [_agent(1), _orch()],
             "edges": [{"source": "a1", "target": "ghost"}]}
    assert "unknown node" in jg._validate_graph(graph)


def test_cycle_rejected():
    # a1 -> a2 -> a1  (plus a1 -> orch so reachability isn't the failure)
    graph = {"task": "t", "nodes": [_agent(1), _agent(2), _orch()],
             "edges": [{"source": "a1", "target": "a2"},
                       {"source": "a2", "target": "a1"},
                       {"source": "a1", "target": "orchestrator"}]}
    assert "cycle" in jg._validate_graph(graph)


def test_dangling_agent_rejected():
    # a2 has no path to orchestrator
    graph = {"task": "t", "nodes": [_agent(1), _agent(2), _orch()],
             "edges": _to_orch("a1")}
    assert "no path" in jg._validate_graph(graph)


def test_orchestrator_with_outgoing_edge_rejected():
    graph = {"task": "t", "nodes": [_agent(1), _orch()],
             "edges": [{"source": "a1", "target": "orchestrator"},
                       {"source": "orchestrator", "target": "a1"}]}
    assert "terminal sink" in jg._validate_graph(graph)


def test_missing_orchestrator_rejected():
    graph = {"task": "t", "nodes": [_agent(1)], "edges": []}
    assert "orchestrator" in jg._validate_graph(graph)


def test_no_agent_nodes_rejected():
    graph = {"task": "t", "nodes": [_orch()], "edges": []}
    assert jg._validate_graph(graph)


def test_too_many_nodes_rejected():
    nodes = [_agent(i) for i in range(jg.MAX_NODES + 1)] + [_orch()]
    edges = _to_orch(*[f"a{i}" for i in range(jg.MAX_NODES + 1)])
    assert "max" in jg._validate_graph({"task": "t", "nodes": nodes, "edges": edges})


# ---------------------------------------------------------------------------
# Task 2 — async topological executor + frame protocol
# ---------------------------------------------------------------------------


def _collect_emit():
    frames = []
    return frames, frames.append


def _fake_call_node(concurrency_box=None):
    """A deterministic call_node: records concurrency and echoes its inputs so
    tests can assert ordering + upstream context without any LLM."""
    async def call(node, system, user, ladder, *, max_tokens, extra_body, emit):
        if concurrency_box is not None:
            concurrency_box["cur"] += 1
            concurrency_box["max"] = max(concurrency_box["max"], concurrency_box["cur"])
        await asyncio.sleep(0.01)  # force overlap so the cap is exercised
        text = f"OUT[{node['id']}] saw_user={user!r}"
        if emit:
            emit({"type": "node_chunk", "node": node["id"], "content": text})
        if concurrency_box is not None:
            concurrency_box["cur"] -= 1
        return {"content": text, "model": ladder[0][1]}
    return call


def test_run_graph_emits_full_frame_protocol():
    graph = {"task": "do x", "nodes": [_agent(1), _agent(2), _orch()],
             "edges": _to_orch("a1", "a2")}
    frames, emit = _collect_emit()
    out = asyncio.run(jg.run_graph(graph, emit=emit, call_node=_fake_call_node()))
    types = [f["type"] for f in frames]
    assert types.count("node_start") == 3
    assert types.count("node_end") == 3
    assert types.count("edge_flow") == 2  # one per edge
    assert types.count("graph_done") == 1
    assert out["output"].startswith("OUT[orchestrator]")
    assert {f["node"] for f in frames if f["type"] == "node_start"} == {"a1", "a2", "orchestrator"}


def test_orchestrator_sees_upstream_outputs():
    graph = {"task": "T", "nodes": [_agent(1), _agent(2), _orch()],
             "edges": _to_orch("a1", "a2")}
    out = asyncio.run(jg.run_graph(graph, call_node=_fake_call_node()))
    assert "OUT[a1]" in out["outputs"]["orchestrator"]
    assert "OUT[a2]" in out["outputs"]["orchestrator"]


def test_chain_runs_in_topological_order():
    # a1 -> a2 -> orchestrator ; a2 must see a1's output, orchestrator only a2's
    graph = {"task": "T", "nodes": [_agent(1), _agent(2), _orch()],
             "edges": [{"source": "a1", "target": "a2"},
                       {"source": "a2", "target": "orchestrator"}]}
    out = asyncio.run(jg.run_graph(graph, call_node=_fake_call_node()))
    assert "OUT[a1]" in out["outputs"]["a2"]            # a2 ran after a1, saw it
    assert "OUT[a2]" in out["outputs"]["orchestrator"]  # orchestrator ran after a2
    # orchestrator's DIRECT upstream is only a2 (a1 reaches it transitively, not directly)
    preds, _ = jg._adjacency(graph["nodes"], graph["edges"])
    assert preds["orchestrator"] == {"a2"}


def test_concurrency_never_exceeds_three():
    nodes = [_agent(i) for i in range(6)] + [_orch()]
    edges = _to_orch(*[f"a{i}" for i in range(6)])
    graph = {"task": "T", "nodes": nodes, "edges": edges}
    box = {"cur": 0, "max": 0}
    asyncio.run(jg.run_graph(graph, call_node=_fake_call_node(box)))
    assert box["max"] <= 3
    assert box["max"] >= 2  # sanity: they did overlap


def test_invalid_graph_emits_error_frame():
    graph = {"task": "T", "nodes": [_agent(1), _orch()],
             "edges": [{"source": "a1", "target": "a1"}]}  # self-cycle
    frames, emit = _collect_emit()
    out = asyncio.run(jg.run_graph(graph, emit=emit, call_node=_fake_call_node()))
    assert out.get("error")
    assert any(f["type"] == "error" for f in frames)
