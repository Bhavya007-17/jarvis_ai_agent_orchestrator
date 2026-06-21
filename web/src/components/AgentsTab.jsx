import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ReactFlow, ReactFlowProvider, Background, Controls, useReactFlow,
  useNodesState, useEdgesState, ConnectionMode,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Play, Save, Trash2 } from 'lucide-react'

import { AGENT_CATALOG, agentById, resolveModel } from '../lib/agents'
import { getBoard, saveBoard } from '../lib/boardApi'
import { fetchModels } from '../lib/chatSocket'
import { runBoardCouncil } from '../lib/boardSocket'
import AgentNode from './board/AgentNode'
import OrchestratorNode from './board/OrchestratorNode'
import PipeEdge from './board/PipeEdge'
import AgentCard from './board/AgentCard'

const MAX_ACTIVE = 3            // NIM free-tier proposer cap (CLAUDE.md)
const ORCH_ID = 'orchestrator'
const nodeTypes = { agent: AgentNode, orchestrator: OrchestratorNode }
const edgeTypes = { pipe: PipeEdge }

const orchestratorNode = {
  id: ORCH_ID, type: 'orchestrator', position: { x: 380, y: 230 },
  data: { status: 'idle', synthesis: '' },
  draggable: true, selectable: false, deletable: false,
}

// First MAX_ACTIVE agent nodes stay wired; the rest are benched (greyed, no pipe).
function normalizeBench(nodes) {
  let active = 0
  return nodes.map((n) => {
    if (n.type !== 'agent') return n
    const benched = active >= MAX_ACTIVE
    if (!benched) active += 1
    return n.data.benched === benched ? n : { ...n, data: { ...n.data, benched } }
  })
}

function Board() {
  const [nodes, setNodes, onNodesChange] = useNodesState([orchestratorNode])
  const [edges, setEdges] = useEdgesState([])
  const [models, setModels] = useState({ task_map: {}, models: [] })
  const [task, setTask] = useState('')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [synthesis, setSynthesis] = useState('')

  const modelsRef = useRef(models)
  const synthRef = useRef('')
  const runRef = useRef(null)
  const { screenToFlowPosition, fitView } = useReactFlow()

  useEffect(() => { modelsRef.current = models }, [models])

  const patchNode = useCallback((id, patch) => {
    setNodes((nds) => nds.map((n) => (n.id === id
      ? { ...n, data: { ...n.data, ...(typeof patch === 'function' ? patch(n.data) : patch) } }
      : n)))
  }, [setNodes])

  const removeAgent = useCallback((id) => {
    setNodes((nds) => normalizeBench(nds.filter((n) => n.id !== id)))
  }, [setNodes])

  const createAgentNode = useCallback((id, agentId, position, model, benched) => {
    const agent = agentById(agentId)
    return {
      id, type: 'agent', position,
      data: {
        agent,
        model: model || resolveModel(agent, modelsRef.current),
        models: modelsRef.current.models || [],
        status: 'idle', tokens: '', benched: !!benched,
        onRemove: () => removeAgent(id),
        onModelChange: (m) => patchNode(id, { model: m }),
      },
    }
  }, [removeAgent, patchNode])

  const addAgent = useCallback((agentId, position) => {
    if (!agentById(agentId)) return
    const id = `a_${agentId}_${Date.now()}`
    setNodes((nds) => {
      // Drop = explicit position; click-add = stack in a left column (stays in
      // view; the orchestrator sits to the right so pipes flow left->center).
      let pos = position
      if (!pos) {
        const i = nds.filter((n) => n.type === 'agent').length
        pos = { x: 60, y: 60 + (i % 4) * 140 }
      }
      return normalizeBench([...nds, createAgentNode(id, agentId, pos)])
    })
  }, [createAgentNode, setNodes])

  // Edges are derived from the nodes: one pipe per active agent, its status (and
  // accent) read straight off the node — so a status patch recolors the pipe.
  useEffect(() => {
    const active = nodes.filter((n) => n.type === 'agent' && !n.data.benched)
    setEdges(active.map((n) => ({
      id: `e_${n.id}`, source: ORCH_ID, target: n.id, type: 'pipe',
      data: { accent: n.data.agent.accent, status: n.data.status },
    })))
  }, [nodes, setEdges])

  // Load models, then restore the saved board.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const m = await fetchModels()
      if (cancelled) return
      setModels(m)
      modelsRef.current = m
      const saved = await getBoard()
      if (cancelled || !saved.nodes || saved.nodes.length === 0) return
      const restored = saved.nodes
        .filter((sn) => agentById(sn.persona))
        .map((sn) => createAgentNode(sn.id, sn.persona, { x: sn.x ?? 140, y: sn.y ?? 140 },
          sn.model, sn.benched))
      setNodes(normalizeBench([orchestratorNode, ...restored]))
    })()
    return () => { cancelled = true }
  }, [createAgentNode, setNodes])

  // Keep model dropdowns in sync once /api/models resolves.
  useEffect(() => {
    setNodes((nds) => nds.map((n) => (n.type === 'agent'
      ? { ...n, data: { ...n.data, models: models.models || [] } } : n)))
  }, [models, setNodes])

  // Reframe so every placed agent stays in view (fitView only auto-runs on mount).
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
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }, [])

  const resetStatuses = useCallback(() => {
    setNodes((nds) => nds.map((n) => (n.type === 'agent'
      ? { ...n, data: { ...n.data, status: 'idle', tokens: '' } } : n)))
    patchNode(ORCH_ID, { status: 'idle' })
  }, [setNodes, patchNode])

  const onFrame = useCallback((f) => {
    if (f.type === 'error') {
      setError(f.detail || 'Council failed')
      setRunning(false)
      resetStatuses()
      return
    }
    const label = f.label || ''
    // Proposer frames are labelled "PROPOSAL <n> — <persona>"; map by the index
    // (robust to persona/dash quirks) to the node placed in that roster slot.
    const order = runRef.current?.order || []
    const m = label.match(/^PROPOSAL (\d+)/)
    const proposerId = m ? order[Number(m[1]) - 1] : null
    const isSynthPhase = label.startsWith('CRITIQUE') || label.startsWith('SYNTHESIZED')

    if (f.type === 'voice_start') {
      if (proposerId) patchNode(proposerId, { status: 'pulsing', tokens: '' })
      if (isSynthPhase) patchNode(ORCH_ID, { status: 'busy' })
    } else if (f.type === 'voice_chunk') {
      if (proposerId) patchNode(proposerId, (d) => ({ tokens: (d.tokens || '') + f.content }))
      if (label.startsWith('SYNTHESIZED')) {
        synthRef.current += f.content
        setSynthesis(synthRef.current)
      }
    } else if (f.type === 'voice_end') {
      if (proposerId) patchNode(proposerId, { status: 'done' })
    } else if (f.type === 'council_done') {
      setRunning(false)
      patchNode(ORCH_ID, { status: 'idle', synthesis: synthRef.current })
    }
  }, [patchNode, resetStatuses])

  const runCouncil = useCallback(() => {
    const q = task.trim()
    if (!q) { setError('Type a task for the agents to plan.'); return }
    const active = nodes.filter((n) => n.type === 'agent' && !n.data.benched)
    if (active.length === 0) { setError('Drop at least one agent onto the board first.'); return }
    setError('')
    setSynthesis('')
    synthRef.current = ''
    const roster = active.map((n) => ({
      persona: n.data.agent.persona, lens: n.data.agent.lens, model: n.data.model,
    }))
    runRef.current = { order: active.map((n) => n.id) }
    resetStatuses()
    setRunning(true)
    runBoardCouncil({ task: q, roster, onFrame, onClose: () => setRunning(false) })
  }, [task, nodes, onFrame, resetStatuses])

  const onSave = useCallback(async () => {
    const agentNodes = nodes.filter((n) => n.type === 'agent')
    const payload = {
      nodes: agentNodes.map((n) => ({
        id: n.id, persona: n.data.agent.id, model: n.data.model,
        x: Math.round(n.position.x), y: Math.round(n.position.y), benched: !!n.data.benched,
      })),
      edges: edges.map((e) => ({ id: e.id, source: e.source, target: e.target })),
      models: Object.fromEntries(agentNodes.map((n) => [n.data.agent.id, n.data.model])),
    }
    const res = await saveBoard(payload)
    setError(res.ok ? '' : `Save failed: ${res.message || 'unknown error'}`)
  }, [nodes, edges])

  const onClear = useCallback(() => {
    setNodes([orchestratorNode])
    setSynthesis('')
    synthRef.current = ''
  }, [setNodes])

  const activeCount = nodes.filter((n) => n.type === 'agent' && !n.data.benched).length

  return (
    <div className="flex h-full min-h-0">
      {/* palette */}
      <aside className="w-52 shrink-0 glass border-y-0 border-l-0 flex flex-col">
        <div className="px-3 py-3 border-b border-core/10">
          <div className="eyebrow">agent library</div>
          <div className="tag mt-1">drag onto the board · {activeCount}/{MAX_ACTIVE} active</div>
        </div>
        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
          {AGENT_CATALOG.map((a) => <AgentCard key={a.id} agent={a} onAdd={addAgent} />)}
        </div>
      </aside>

      {/* canvas + task bar */}
      <div className="flex-1 min-w-0 flex flex-col">
        <div className="flex-1 min-h-0 relative" onDrop={onDrop} onDragOver={onDragOver}>
          <ReactFlow
            nodes={nodes} edges={edges}
            onNodesChange={onNodesChange}
            nodeTypes={nodeTypes} edgeTypes={edgeTypes}
            connectionMode={ConnectionMode.Loose}
            nodesConnectable={false}
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
              onKeyDown={(e) => { if (e.key === 'Enter' && !running) runCouncil() }}
              placeholder="Give the board a task — every active agent weighs in…"
              className="flex-1 hud-input px-3 py-2 text-sm"
              disabled={running}
            />
            <button className="hud-btn px-4 py-2 text-sm" onClick={runCouncil} disabled={running}>
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
