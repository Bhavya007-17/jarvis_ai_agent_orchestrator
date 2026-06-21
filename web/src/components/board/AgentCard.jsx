// A draggable library card. On drag, it stashes the agent id; AgentsTab reads it
// on drop to place a node. Also clickable (keyboard-friendly) to add to center.
export default function AgentCard({ agent, onAdd }) {
  const onDragStart = (e) => {
    e.dataTransfer.setData('application/jarvis-agent', agent.id)
    e.dataTransfer.effectAllowed = 'move'
  }

  return (
    <button
      draggable
      onDragStart={onDragStart}
      onClick={() => onAdd && onAdd(agent.id)}
      className="w-full text-left rounded-lg px-3 py-2 glass hover:border-core/40 transition-colors cursor-grab active:cursor-grabbing"
      style={{ borderColor: `${agent.accent}44` }}
      title={`Add ${agent.persona}`}
      aria-label={`Add ${agent.persona}`}
    >
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full shrink-0"
          style={{ background: agent.accent, boxShadow: `0 0 8px ${agent.accent}` }} />
        <span className="font-display text-sm font-semibold tracking-wide"
          style={{ color: agent.accent }}>{agent.persona}</span>
      </div>
      <div className="mt-0.5 text-[11px] text-[#7FA3B2] leading-tight">{agent.blurb}</div>
    </button>
  )
}
