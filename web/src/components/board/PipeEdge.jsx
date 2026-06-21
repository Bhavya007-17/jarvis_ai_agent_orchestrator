import { getBezierPath, useInternalNode } from '@xyflow/react'
import { getEdgeParams } from './floatingEdge'

// A connection between the orchestrator and an agent. Three visual states:
//   idle    — dim static pipe
//   pulsing — bright pipe with flowing dashes (agent is streaming)
//   done    — solid bright pipe (agent finished its proposal)
export default function PipeEdge({ id, source, target, data }) {
  const sourceNode = useInternalNode(source)
  const targetNode = useInternalNode(target)
  if (!sourceNode || !targetNode) return null

  const { sx, sy, tx, ty } = getEdgeParams(sourceNode, targetNode)
  const [path] = getBezierPath({ sourceX: sx, sourceY: sy, targetX: tx, targetY: ty })

  const status = data?.status || 'idle'
  const accent = data?.accent || '#22d3ee'
  const baseOpacity = status === 'idle' ? 0.22 : status === 'done' ? 0.7 : 0.45

  return (
    <>
      <path
        id={id}
        d={path}
        fill="none"
        stroke={accent}
        strokeWidth={2}
        style={{ opacity: baseOpacity, filter: `drop-shadow(0 0 4px ${accent})` }}
      />
      {status === 'pulsing' && (
        <path
          d={path}
          fill="none"
          stroke={accent}
          strokeWidth={2.5}
          className="rf-pipe-pulse"
          style={{ filter: `drop-shadow(0 0 6px ${accent})` }}
        />
      )}
    </>
  )
}
