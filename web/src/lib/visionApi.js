// web/src/lib/visionApi.js
// Vision face-auth API - server owns the compare + enrolled vector (presence only).
const BASE = 'http://localhost:8700'

async function jpost(path, body, method = 'POST') {
  try {
    const r = await fetch(BASE + path, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return await r.json()
  } catch (e) {
    return { ok: false, message: String(e) }
  }
}

export async function getStatus() {
  try {
    const r = await fetch(BASE + '/api/vision/status')
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return await r.json()
  } catch (e) {
    return { enrolled: false, lock_enabled: false, error: String(e) }
  }
}

export const enroll = (vector) => jpost('/api/vision/enroll', { vector })
export const verify = (vector) => jpost('/api/vision/verify', { vector })
export const setLock = (enabled) => jpost('/api/vision/lock', { enabled }, 'PUT')
