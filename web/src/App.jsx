import { useState } from 'react'
import ReactorCore from './components/ReactorCore'
import BottomBar from './shell/BottomBar'
import ModuleWindow from './shell/ModuleWindow'
import { useWindows } from './shell/useWindows'
import { MODULE_BY_ID } from './shell/modules'

export default function App() {
  const [model, setModel] = useState('auto')
  const { windows, isOpen, toggle, focus, move, close } = useWindows()
  const shellProps = { model, setModel }

  return (
    <div className="relative h-screen w-screen overflow-hidden hud-field text-[#CBE7F0]">
      {/* ambient layers */}
      <div className="pointer-events-none absolute inset-0 hud-grid" />
      <div className="pointer-events-none absolute inset-x-0 top-0 scanline animate-scan opacity-40" />

      {/* central idle HUD backdrop */}
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-3">
        <ReactorCore size={150} active />
        <div className="font-display text-2xl font-bold tracking-[0.3em] text-core drop-shadow-[0_0_12px_rgba(34,211,238,0.6)]">
          JARVIS
        </div>
        <div className="eyebrow">multi-model core</div>
      </div>

      {/* floating module windows */}
      {windows.map((w) => {
        const mod = MODULE_BY_ID[w.id]
        if (!mod) return null
        const { Component, defaultRect, props = [] } = mod
        const childProps = Object.fromEntries(props.map((k) => [k, shellProps[k]]))
        return (
          <ModuleWindow
            key={w.id}
            id={w.id}
            title={mod.label}
            icon={mod.icon}
            x={w.x}
            y={w.y}
            z={w.z}
            w={defaultRect.w}
            h={defaultRect.h}
            onFocus={focus}
            onMove={move}
            onClose={close}
          >
            <Component {...childProps} />
          </ModuleWindow>
        )
      })}

      <BottomBar isOpen={isOpen} onToggle={toggle} />
    </div>
  )
}
