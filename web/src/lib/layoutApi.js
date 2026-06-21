// Shell layout persistence — server-side only (no localStorage, per CLAUDE.md).
// Mirrors the sidecar's GET/PUT /api/ui-layout endpoints.

const BASE = 'http://localhost:8700'

/** Load the saved layout. Returns {windows:{}} (never throws) on any failure. */
export async function getLayout() {
  try {
    const r = await fetch(BASE + '/api/ui-layout')
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return await r.json()
  } catch (e) {
    return { windows: {}, error: String(e) }
  }
}

/**
 * Persist the layout. Returns {ok, layout} on success or {ok:false, message}.
 * @param {{windows: Record<string, {x:number,y:number,open:boolean,z:number}>}} layout
 */
export async function saveLayout(layout) {
  try {
    const r = await fetch(BASE + '/api/ui-layout', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(layout),
    })
    return await r.json()
  } catch (e) {
    return { ok: false, message: String(e) }
  }
}
