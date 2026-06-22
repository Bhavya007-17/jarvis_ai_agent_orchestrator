// web/src/lib/clickyApi.js
// Clicky: ask "where is X on screen" -> server captures + a vision model points.
const BASE = 'http://localhost:8700'

export async function point(question) {
  try {
    const r = await fetch(BASE + '/api/clicky/point', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return await r.json()
  } catch (e) {
    return { found: false, point: null, screenshot_b64: null, description: String(e) }
  }
}
