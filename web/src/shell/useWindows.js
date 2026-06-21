import { useCallback, useEffect, useRef, useState } from 'react'
import { getLayout, saveLayout } from '../lib/layoutApi'
import { MODULE_BY_ID } from './modules'

// Clamp a center-anchored window so it stays within the viewport.
function clamp(x, y, w, h) {
  const margin = 12
  const barH = 92 // bottom bar reserve
  const maxX = Math.max(margin + w / 2, window.innerWidth - w / 2 - margin)
  const maxY = Math.max(margin + h / 2, window.innerHeight - h / 2 - barH)
  return {
    x: Math.min(Math.max(w / 2 + margin, x), maxX),
    y: Math.min(Math.max(h / 2 + margin, y), maxY),
  }
}

export function useWindows() {
  // state shape: { [id]: { x, y, z, open } } for ALL known modules touched so far
  const [state, setState] = useState({})
  const zTop = useRef(30)
  const saveTimer = useRef(null)
  const loaded = useRef(false)

  // Restore once on mount.
  useEffect(() => {
    let cancelled = false
    getLayout().then((data) => {
      if (cancelled) return
      const wins = data?.windows || {}
      const next = {}
      let maxZ = 30
      for (const [id, w] of Object.entries(wins)) {
        if (!MODULE_BY_ID[id]) continue
        const rect = MODULE_BY_ID[id].defaultRect
        const { x, y } = clamp(w.x, w.y, rect.w, rect.h)
        const z = Number.isInteger(w.z) ? w.z : 30
        next[id] = { x, y, z, open: !!w.open }
        if (z > maxZ) maxZ = z
      }
      zTop.current = maxZ
      loaded.current = true
      setState(next)
    })
    return () => { cancelled = true }
  }, [])

  // Debounced persist whenever state changes (after the initial restore).
  useEffect(() => {
    if (!loaded.current) return
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => {
      saveLayout({ windows: state })
    }, 400)
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current) }
  }, [state])

  const open = useCallback((id) => {
    const mod = MODULE_BY_ID[id]
    if (!mod) return
    setState((prev) => {
      const z = ++zTop.current
      const existing = prev[id]
      if (existing) return { ...prev, [id]: { ...existing, open: true, z } }
      const r = mod.defaultRect
      const { x, y } = clamp(r.x + r.w / 2, r.y + r.h / 2, r.w, r.h)
      return { ...prev, [id]: { x, y, z, open: true } }
    })
  }, [])

  const close = useCallback((id) => {
    setState((prev) => (prev[id] ? { ...prev, [id]: { ...prev[id], open: false } } : prev))
  }, [])

  const isOpen = useCallback((id) => !!state[id]?.open, [state])

  const toggle = useCallback((id) => {
    if (state[id]?.open) close(id)
    else open(id)
  }, [state, open, close])

  const focus = useCallback((id) => {
    setState((prev) => (prev[id] ? { ...prev, [id]: { ...prev[id], z: ++zTop.current } } : prev))
  }, [])

  const move = useCallback((id, x, y) => {
    const mod = MODULE_BY_ID[id]
    const r = mod ? mod.defaultRect : { w: 400, h: 400 }
    const c = clamp(x, y, r.w, r.h)
    setState((prev) => (prev[id] ? { ...prev, [id]: { ...prev[id], x: c.x, y: c.y } } : prev))
  }, [])

  const windows = Object.entries(state)
    .filter(([, w]) => w.open)
    .map(([id, w]) => ({ id, ...w }))
    .sort((a, b) => a.z - b.z)

  return { windows, isOpen, toggle, open, close, focus, move }
}
