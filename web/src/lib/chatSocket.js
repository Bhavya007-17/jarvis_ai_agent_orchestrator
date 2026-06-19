const SIDECAR_WS = 'ws://localhost:8700/api/chat'

// Opens a one-shot chat stream. Calls onFrame for every JSON frame
// ({type: 'rung'|'chunk'|'done'|'error', ...}). Returns the socket.
export function sendChat({ message, model, onFrame, onClose }) {
  const ws = new WebSocket(SIDECAR_WS)
  ws.onopen = () => ws.send(JSON.stringify({ message, model }))
  ws.onmessage = (e) => {
    let frame
    try { frame = JSON.parse(e.data) } catch { return }
    onFrame(frame)
    if (frame.type === 'done' || frame.type === 'error') ws.close()
  }
  ws.onerror = () => onFrame({ type: 'error', detail: 'WebSocket connection failed' })
  ws.onclose = () => onClose && onClose()
  return ws
}

export async function fetchModels() {
  try {
    const r = await fetch('http://localhost:8700/api/models')
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return await r.json()
  } catch {
    return { task_map: {}, models: ['auto'] }
  }
}
