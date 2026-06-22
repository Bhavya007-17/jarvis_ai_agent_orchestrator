// Runs an agent GRAPH over /api/graph. Sends the full {task, nodes, edges} the
// user drew; receives node-id-keyed frames so the board animates per node + edge.
// Frames: node_start / node_chunk / node_end / edge_flow / graph_done / error.

/**
 * @param {Object} opts
 * @param {string} opts.task
 * @param {{id:string,persona:string,lens?:string,model?:string}[]} opts.nodes
 * @param {{source:string,target:string}[]} opts.edges
 * @param {(frame: object) => void} opts.onFrame
 * @param {() => void} [opts.onClose]
 * @returns {WebSocket}
 */
export function runGraph({ task, nodes, edges, onFrame, onClose }) {
  const ws = new WebSocket('ws://localhost:8700/api/graph')
  ws.onopen = () => ws.send(JSON.stringify({ task, nodes, edges }))
  ws.onmessage = (e) => {
    let frame
    try { frame = JSON.parse(e.data) } catch { return }
    onFrame(frame)
    if (frame.type === 'graph_done' || frame.type === 'error') ws.close()
  }
  ws.onerror = () => onFrame({ type: 'error', detail: 'Graph WS failed' })
  ws.onclose = () => onClose && onClose()
  return ws
}
