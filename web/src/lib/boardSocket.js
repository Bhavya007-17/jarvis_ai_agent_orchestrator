// Runs a council over the board's roster. Same /api/council WS the Council tab
// uses, but carries a `roster` of {persona, lens, model} so the orchestrator
// deliberates over exactly the agents placed on the board.
// Frames: voice_start / voice_chunk / voice_end / council_done / error.

/**
 * @param {Object}   opts
 * @param {string}   opts.task
 * @param {{persona:string,lens:string,model:string}[]} opts.roster
 * @param {boolean} [opts.execute]
 * @param {(frame: object) => void} opts.onFrame
 * @param {() => void} [opts.onClose]
 * @returns {WebSocket}
 */
export function runBoardCouncil({ task, roster, execute = false, onFrame, onClose }) {
  const ws = new WebSocket('ws://localhost:8700/api/council')
  ws.onopen = () => ws.send(JSON.stringify({ task, roster, execute }))
  ws.onmessage = (e) => {
    let frame
    try { frame = JSON.parse(e.data) } catch { return }
    onFrame(frame)
    if (frame.type === 'council_done' || frame.type === 'error') ws.close()
  }
  ws.onerror = () => onFrame({ type: 'error', detail: 'Council WS failed' })
  ws.onclose = () => onClose && onClose()
  return ws
}
