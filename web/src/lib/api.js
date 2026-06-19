const BASE = 'http://localhost:8700'

export async function getJSON(path) {
  try {
    const r = await fetch(BASE + path)
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return await r.json()
  } catch (e) { return { error: String(e) } }
}

export async function postJSON(path, body) {
  try {
    const r = await fetch(BASE + path, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    })
    return await r.json()
  } catch (e) { return { ok: false, message: String(e) } }
}

export async function delJSON(path) {
  try { const r = await fetch(BASE + path, { method: 'DELETE' }); return await r.json() }
  catch (e) { return { ok: false, message: String(e) } }
}

// Council streams over its own WS; frames: voice_start / voice_chunk / voice_end / council_done / error
export function openCouncil({ task, execute, onFrame, onClose }) {
  const ws = new WebSocket('ws://localhost:8700/api/council')
  ws.onopen = () => ws.send(JSON.stringify({ task, execute }))
  ws.onmessage = (e) => {
    let f
    try { f = JSON.parse(e.data) } catch { return }
    onFrame(f)
    if (f.type === 'council_done' || f.type === 'error') ws.close()
  }
  ws.onerror = () => onFrame({ type: 'error', detail: 'Council WS failed' })
  ws.onclose = () => onClose && onClose()
  return ws
}

export const GRAPH_URL = 'http://localhost:9749'
