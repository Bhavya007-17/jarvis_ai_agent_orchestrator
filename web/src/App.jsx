import { useEffect, useState } from 'react'
import ReactorCore from './components/ReactorCore'
import BottomBar from './shell/BottomBar'
import ModuleWindow from './shell/ModuleWindow'
import AuthLock from './components/AuthLock'
import { useWindows } from './shell/useWindows'
import { MODULE_BY_ID } from './shell/modules'
import { getStatus } from './lib/visionApi'

export default function App() {
  const [model, setModel] = useState('auto')
  const [locked, setLocked] = useState(false)
  const [checked, setChecked] = useState(false)
  const { windows, isOpen, toggle, open, close, focus, move } = useWindows()

  useEffect(() => {
    getStatus().then((s) => {
      setLocked(!!(s.enrolled && s.lock_enabled))
      setChecked(true)
    })
  }, [])

  // Gesture -> window action map (window control).
  const onGestureAction = (g) => {
    if (g === 'Open Palm') open('chat')
    else if (g === 'Peace Sign') open('voice')
    else if (g === 'Pinching') toggle('vision')
    else if (g === 'Closed Fist') {
      const top = [...windows].sort((a, b) => b.z - a.z)[0]
      if (top) close(top.id)
    }
  }

  const fakeFace = typeof window !== 'undefined' && window.__VISION_FAKE__ && window.__VISION_FAKE__.faceFactory
  const shellProps = { model, setModel, onGestureAction }

  if (checked && locked) {
    return <AuthLock onUnlock={() => setLocked(false)} recognizerFactory={fakeFace || undefined} />
  }

  return (
    <div className="relative h-screen w-screen overflow-hidden hud-field text-[#CBE7F0]">
      <div className="pointer-events-none absolute inset-0 hud-grid" />
      <div className="pointer-events-none absolute inset-x-0 top-0 scanline animate-scan opacity-40" />
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-3">
        <ReactorCore size={150} active />
        <div className="font-display text-2xl font-bold tracking-[0.3em] text-core drop-shadow-[0_0_12px_rgba(34,211,238,0.6)]">JARVIS</div>
        <div className="eyebrow">multi-model core</div>
      </div>
      {windows.map((w) => {
        const mod = MODULE_BY_ID[w.id]
        if (!mod) return null
        const { Component, defaultRect, props = [] } = mod
        const childProps = Object.fromEntries(props.map((k) => [k, shellProps[k]]))
        return (
          <ModuleWindow key={w.id} id={w.id} title={mod.label} icon={mod.icon}
            x={w.x} y={w.y} z={w.z} w={defaultRect.w} h={defaultRect.h}
            onFocus={focus} onMove={move} onClose={close}>
            <Component {...childProps} />
          </ModuleWindow>
        )
      })}
      <BottomBar isOpen={isOpen} onToggle={toggle} />
    </div>
  )
}
