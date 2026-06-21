import { Handle, Position } from '@xyflow/react'
import ReactorCore from '../ReactorCore'

// The fixed center node. Pipes radiate from here to each placed agent; when the
// council finishes, the synthesized plan surfaces in its readout.
export default function OrchestratorNode({ data }) {
  const { status = 'idle', synthesis = '' } = data
  const busy = status === 'busy'

  return (
    <div className="relative grid place-items-center w-[150px] h-[150px] rounded-full glass"
      style={{ boxShadow: busy ? '0 0 28px rgba(34,211,238,0.5)' : '0 0 16px rgba(34,211,238,0.25)' }}>
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />

      <div className="flex flex-col items-center gap-1">
        <ReactorCore size={64} active={busy} />
        <div className="font-display text-[11px] font-bold tracking-[0.28em] text-core">
          ORCHESTRATOR
        </div>
        <div className="tag">{busy ? 'synthesizing…' : synthesis ? 'plan ready' : 'idle'}</div>
      </div>
    </div>
  )
}
