// Agent Board persistence — server-side only (no localStorage, per CLAUDE.md).
// Mirrors the sidecar's GET/PUT /api/board endpoints.

const BASE = 'http://localhost:8700'

/** Load the saved board. Returns an empty board (never throws) on any failure. */
export async function getBoard() {
  try {
    const r = await fetch(BASE + '/api/board')
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return await r.json()
  } catch (e) {
    return { nodes: [], edges: [], models: {}, error: String(e) }
  }
}

/**
 * Persist the board. Returns {ok, board} on success or {ok:false, message}.
 * @param {{nodes: object[], edges: object[], models: Record<string,string>}} board
 */
export async function saveBoard(board) {
  try {
    const r = await fetch(BASE + '/api/board', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(board),
    })
    return await r.json()
  } catch (e) {
    return { ok: false, message: String(e) }
  }
}
