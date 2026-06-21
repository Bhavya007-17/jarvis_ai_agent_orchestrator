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
