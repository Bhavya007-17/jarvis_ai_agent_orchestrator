import { Handle, Position } from '@xyflow/react'
import { X } from 'lucide-react'

// A placed agent on the board. Hidden handles let React Flow attach the pipe;
// the floating edge ignores their position, so one source + one target suffices.
const STATUS_LABEL = { idle: 'idle', pulsing: 'thinking…', done: 'done' }

export default function AgentNode({ data }) {
  const { agent, model, models = [], status = 'idle', tokens = '',
          benched = false, onRemove, onModelChange } = data
  const accent = agent.accent

  return (
    <div
      className={`relative w-[176px] rounded-xl px-3 py-2.5 glass transition-opacity ${benched ? 'opacity-45' : ''}`}
      style={{ borderColor: `${accent}66`, boxShadow: status === 'pulsing' ? `0 0 18px ${accent}55` : undefined }}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />

      <button
        onClick={() => onRemove && onRemove()}
        className="absolute -top-2 -right-2 grid place-items-center h-5 w-5 rounded-full bg-[#0a121c] border border-core/30 text-[#7FA3B2] hover:text-core"
        title="Remove agent" aria-label={`Remove ${agent.persona}`}
      >
        <X size={11} />
      </button>

      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full shrink-0"
          style={{ background: accent, boxShadow: `0 0 8px ${accent}` }} />
        <span className="font-display text-sm font-semibold tracking-wide truncate"
          style={{ color: accent }}>{agent.persona}</span>
      </div>

      <select
        value={model}
        onChange={(e) => onModelChange && onModelChange(e.target.value)}
        className="mt-2 w-full hud-input text-[10px] px-1.5 py-1 nodrag"
        title="Model for this agent"
      >
        {models.filter((m) => m && m !== 'auto').map((m) => (
          <option key={m} value={m}>{m}</option>
        ))}
        {model && !models.includes(model) && <option value={model}>{model}</option>}
      </select>

      <div className="mt-2 flex items-center gap-1.5">
        <span className={`h-1.5 w-1.5 rounded-full ${status === 'pulsing' ? 'animate-pulse' : ''}`}
          style={{ background: benched ? '#475569' : accent }} />
        <span className="tag">{benched ? 'benched' : STATUS_LABEL[status]}</span>
      </div>

      {status === 'pulsing' && tokens && (
        <div className="mt-1.5 h-8 overflow-hidden text-[10px] leading-tight text-[#9FD8E4]/80 font-mono">
          {tokens.slice(-90)}
        </div>
      )}
    </div>
  )
}
