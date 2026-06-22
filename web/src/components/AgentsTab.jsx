import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ReactFlow, ReactFlowProvider, Background, Controls, useReactFlow,
  useNodesState, useEdgesState, addEdge, ConnectionMode,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Play, Save, Trash2 } from 'lucide-react'

import { agentsByCategory, agentById, resolveModel } from '../lib/agents'
import { getBoard, saveBoard } from '../lib/boardApi'
import { fetchModels } from '../lib/chatSocket'
import { runGraph } from '../lib/graphSocket'
import AgentNode from './board/AgentNode'
import OrchestratorNode from './board/OrchestratorNode'
import PipeEdge from './board/PipeEdge'
import AgentCard from './board/AgentCard'

const ORCH_ID = 'orchestrator'
const nodeTypes = { agent: AgentNode, orchestrator: OrchestratorNode }
const edgeTypes = { pipe: PipeEdge }

const orchestratorNode = {
  id: ORCH_ID, type: 'orchestrator', position: { x: 520, y: 240 },
  data: { status: 'idle', synthesis: '' },
  draggable: true, selectable: false, deletable: false,
}

function feedEdge(source, target, accent = '#22d3ee') {
  return { id: `e_${source}__${target}`, source, target, type: 'pipe',
           data: { accent, status: 'idle', kind: 'feeds' } }
}

function Board() {
  const [nodes, setNodes, onNodesChange] = useNodesState([orchestratorNode])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [models, setModels] = useState({ task_map: {}, models: [] })
  const [task, setTask] = useState('')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [synthesis, setSynthesis] = useState('')

  const modelsRef = useRef(models)
  const synthRef = useRef('')
  const { screenToFlowPosition, fitView } = useReactFlow()

  useEffect(() => { modelsRef.current = models }, [models])

  const patchNode = useCallback((id, patch) => {
    setNodes((nds) => nds.map((n) => (n.id === id
      ? { ...n, data: { ...n.data, ...(typeof patch === 'function' ? patch(n.data) : patch) } }
      : n)))
  }, [setNodes])

  const pulseEdge = useCallback((source, target) => {
    setEdges((eds) => eds.map((e) => (e.source === source && e.target === target
      ? { ...e, data: { ...e.data, status: 'pulsing' } } : e)))
    setTimeout(() => {
      setEdges((eds) => eds.map((e) => (e.source === source && e.target === target
        ? { ...e, data: { ...e.data, status: 'done' } } : e)))
    }, 700)
  }, [setEdges])

  const removeAgent = useCallback((id) => {
    setNodes((nds) => nds.filter((n) => n.id !== id))
    setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id))
  }, [setNodes, setEdges])

  const createAgentNode = useCallback((id, agentId, position, model) => {
    const agent = agentById(agentId)
    return {
      id, type: 'agent', position,
      data: {
        agent,
        model: model || resolveModel(agent, modelsRef.current),
        models: modelsRef.current.models || [],
        status: 'idle', tokens: '',
        onRemove: () => removeAgent(id),
        onModelChange: (m) => patchNode(id, { model: m }),
      },
    }
  }, [removeAgent, patchNode])

  const addAgent = useCallback((agentId, position) => {
    const agent = agentById(agentId)
    if (!agent) return
    const id = `a_${agentId}_${Date.now()}`
    setNodes((nds) => {
      let pos = position
      if (!pos) {
        const i = nds.filter((n) => n.type === 'agent').length
        pos = { x: 60, y: 60 + (i % 5) * 120 }
      }
      return [...nds, createAgentNode(id, agentId, pos)]
    })
    // default wiring: new agent feeds the orchestrator (flat board = council case)
    setEdges((eds) => addEdge(feedEdge(id, ORCH_ID, agent.accent), eds))
  }, [createAgentNode, setNodes, setEdges])

  // User draws an edge between two handles -> a "feeds" edge.
  const onConnect = useCallback((params) => {
    if (!params.source || !params.target || params.source === params.target) return
    const srcAgentId = nodes.find((n) => n.id === params.source)?.data?.agent?.id
    const accent = agentById(srcAgentId)?.accent || '#22d3ee'
    setEdges((eds) => addEdge(feedEdge(params.source, params.target, accent), eds))
  }, [nodes, setEdges])

  // Load models, then restore the saved board (nodes + drawn edges).
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const m = await fetchModels()
      if (cancelled) return
      setModels(m); modelsRef.current = m
      const saved = await getBoard()
      if (cancelled || !saved.nodes || saved.nodes.length === 0) return
      const restored = saved.nodes
        .filter((sn) => agentById(sn.persona))
        .map((sn) => createAgentNode(sn.id, sn.persona,
          { x: sn.x ?? 140, y: sn.y ?? 140 }, sn.model))
      setNodes([orchestratorNode, ...restored])
      const restoredEdges = (saved.edges || [])
        .filter((e) => e.source && e.target)
        .map((e) => feedEdge(e.source, e.target))
      setEdges(restoredEdges)
    })()
    return () => { cancelled = true }
  }, [createAgentNode, setNodes, setEdges])

  // Keep model dropdowns in sync once /api/models resolves.
  useEffect(() => {
    setNodes((nds) => nds.map((n) => (n.type === 'agent'
      ? { ...n, data: { ...n.data, models: models.models || [] } } : n)))
  }, [models, setNodes])

  const agentCount = nodes.filter((n) => n.type === 'agent').length
  useEffect(() => {
    if (agentCount === 0) return undefined
    const t = setTimeout(() => fitView({ padding: 0.25, duration: 300 }), 60)
    return () => clearTimeout(t)
  }, [agentCount, fitView])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    const agentId = e.dataTransfer.getData('application/jarvis-agent')
    if (!agentId) return
    addAgent(agentId, screenToFlowPosition({ x: e.clientX, y: e.clientY }))
  }, [addAgent, screenToFlowPosition])

  const onDragOver = useCallback((e) => {
    e.preventDefault(); e.dataTransfer.dropEffect = 'move'
  }, [])

  const resetStatuses = useCallback(() => {
    setNodes((nds) => nds.map((n) => (n.type === 'agent'
      ? { ...n, data: { ...n.data, status: 'idle', tokens: '' } } : n)))
    setEdges((eds) => eds.map((e) => ({ ...e, data: { ...e.data, status: 'idle' } })))
    patchNode(ORCH_ID, { status: 'idle' })
  }, [setNodes, setEdges, patchNode])

  const onFrame = useCallback((f) => {
    if (f.type === 'error') {
      setError(f.detail || 'Graph failed'); setRunning(false); resetStatuses(); return
    }
    if (f.type === 'node_start') {
      if (f.node === ORCH_ID) patchNode(ORCH_ID, { status: 'busy' })
      else patchNode(f.node, { status: 'pulsing', tokens: '' })
    } else if (f.type === 'node_chunk') {
      if (f.node === ORCH_ID) { synthRef.current += f.content; setSynthesis(synthRef.current) }
      else patchNode(f.node, (d) => ({ tokens: (d.tokens || '') + f.content }))
    } else if (f.type === 'node_end') {
      if (f.node !== ORCH_ID) patchNode(f.node, { status: 'done' })
    } else if (f.type === 'edge_flow') {
      pulseEdge(f.source, f.target)
    } else if (f.type === 'graph_done') {
      setRunning(false)
      patchNode(ORCH_ID, { status: 'idle', synthesis: f.output || synthRef.current })
      if (f.output) { synthRef.current = f.output; setSynthesis(f.output) }
    }
  }, [patchNode, pulseEdge, resetStatuses])

  const runGraphNow = useCallback(() => {
    const q = task.trim()
    if (!q) { setError('Type a task for the agents to reason over.'); return }
    const agentNodes = nodes.filter((n) => n.type === 'agent')
    if (agentNodes.length === 0) { setError('Drop at least one agent onto the board first.'); return }
    setError(''); setSynthesis(''); synthRef.current = ''
    const payloadNodes = [
      ...agentNodes.map((n) => ({ id: n.id, persona: n.data.agent.persona,
        lens: n.data.agent.lens, model: n.data.model })),
      { id: ORCH_ID, persona: 'Orchestrator' },
    ]
    const payloadEdges = edges.map((e) => ({ source: e.source, target: e.target }))
    resetStatuses(); setRunning(true)
    runGraph({ task: q, nodes: payloadNodes, edges: payloadEdges, onFrame,
               onClose: () => setRunning(false) })
  }, [task, nodes, edges, onFrame, resetStatuses])

  const onSave = useCallback(async () => {
    const agentNodes = nodes.filter((n) => n.type === 'agent')
    const payload = {
      nodes: agentNodes.map((n) => ({
        id: n.id, persona: n.data.agent.id, model: n.data.model,
        x: Math.round(n.position.x), y: Math.round(n.position.y),
      })),
      edges: edges.map((e) => ({ id: e.id, source: e.source, target: e.target })),
      models: Object.fromEntries(agentNodes.map((n) => [n.data.agent.id, n.data.model])),
    }
    const res = await saveBoard(payload)
    setError(res.ok ? '' : `Save failed: ${res.message || 'unknown error'}`)
  }, [nodes, edges])

  const onClear = useCallback(() => {
    setNodes([orchestratorNode]); setEdges([])
    setSynthesis(''); synthRef.current = ''
  }, [setNodes, setEdges])

  const groups = agentsByCategory()

  return (
    <div className="flex h-full min-h-0">
      <aside className="w-56 shrink-0 glass border-y-0 border-l-0 flex flex-col">
        <div className="px-3 py-3 border-b border-core/10">
          <div className="eyebrow">agent library</div>
          <div className="tag mt-1">drag onto the board · ≤3 run at once</div>
        </div>
        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
          {groups.map((g) => (
            <div key={g.category}>
              <div className="eyebrow text-[10px] opacity-70 mb-1">{g.category}</div>
              <div className="space-y-2">
                {g.agents.map((a) => <AgentCard key={a.id} agent={a} onAdd={addAgent} />)}
              </div>
            </div>
          ))}
        </div>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col">
        <div className="flex-1 min-h-0 relative" onDrop={onDrop} onDragOver={onDragOver}>
          <ReactFlow
            nodes={nodes} edges={edges}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={nodeTypes} edgeTypes={edgeTypes}
            connectionMode={ConnectionMode.Loose}
            nodesConnectable
            fitView
            proOptions={{ hideAttribution: true }}
            style={{ background: 'transparent' }}
          >
            <Background color="#22d3ee" gap={28} size={1} style={{ opacity: 0.18 }} />
            <Controls showInteractive={false} />
          </ReactFlow>

          {synthesis && (
            <div className="absolute top-3 right-3 w-80 max-h-[60%] overflow-y-auto glass rounded-xl p-3">
              <div className="eyebrow mb-1">synthesized plan</div>
              <div className="text-xs text-[#CBE7F0] whitespace-pre-wrap leading-relaxed">{synthesis}</div>
            </div>
          )}
        </div>

        <div className="shrink-0 glass border-x-0 border-b-0 px-4 py-3">
          {error && <div className="mb-2 text-xs text-rose-300/90">{error}</div>}
          <div className="flex items-center gap-2">
            <input
              value={task} onChange={(e) => setTask(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !running) runGraphNow() }}
              placeholder="Give the graph a task — agents reason over their upstream inputs…"
              className="flex-1 hud-input px-3 py-2 text-sm" disabled={running}
            />
            <button className="hud-btn px-4 py-2 text-sm" onClick={runGraphNow} disabled={running}>
              <Play size={15} /> {running ? 'Running…' : 'Run'}
            </button>
            <button className="hud-btn-ghost px-3 py-2 text-sm" onClick={onSave} title="Save board">
              <Save size={15} />
            </button>
            <button className="hud-btn-ghost px-3 py-2 text-sm" onClick={onClear} title="Clear board">
              <Trash2 size={15} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function AgentsTab() {
  return (
    <ReactFlowProvider>
      <Board />
    </ReactFlowProvider>
  )
}
