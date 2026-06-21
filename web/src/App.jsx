import { useState } from 'react'
import { motion } from 'framer-motion'
import { MessageSquare, Users, Network, Brain, Wrench, Settings as SettingsIcon, Mic } from 'lucide-react'
import ReactorCore from './components/ReactorCore'
import ChatTab from './components/ChatTab'
import CouncilTab from './components/CouncilTab'
import GraphTab from './components/GraphTab'
import MemoryTab from './components/MemoryTab'
import ToolsTab from './components/ToolsTab'
import SettingsTab from './components/SettingsTab'
import VoiceTab from './components/VoiceTab'

const TABS = [
  { id: 'chat', label: 'Chat', icon: MessageSquare, blurb: 'Streamed answers, tagged with the model that served them' },
  { id: 'voice', label: 'Voice', icon: Mic, blurb: 'Always-on wake word, with barge-in' },
  { id: 'council', label: 'Council', icon: Users, blurb: 'Three models propose in parallel, then synthesize' },
  { id: 'graph', label: 'Connections', icon: Network, blurb: 'Live code graph + the routing ladder' },
  { id: 'memory', label: 'Memory', icon: Brain, blurb: 'Durable facts, recalled across turns' },
  { id: 'tools', label: 'Tools', icon: Wrench, blurb: 'Drop-in MCP servers' },
  { id: 'settings', label: 'Settings', icon: SettingsIcon, blurb: 'Switch models without restart' },
]

export default function App() {
  const [tab, setTab] = useState('chat')
  const [model, setModel] = useState('auto')
  const active = TABS.find((t) => t.id === tab)

  return (
    <div className="relative h-screen w-screen overflow-hidden hud-field text-[#CBE7F0]">
      {/* ambient layers */}
      <div className="pointer-events-none absolute inset-0 hud-grid" />
      <div className="pointer-events-none absolute inset-x-0 top-0 scanline animate-scan opacity-40" />

      <div className="relative z-10 flex h-full">
        {/* ── HUD rail ─────────────────────────────────────────── */}
        <nav className="w-56 shrink-0 glass border-y-0 border-l-0 flex flex-col">
          <div className="flex flex-col items-center gap-2 px-4 pt-6 pb-5 border-b border-core/10">
            <ReactorCore size={58} active />
            <div className="font-display text-xl font-bold tracking-[0.3em] text-core drop-shadow-[0_0_12px_rgba(34,211,238,0.6)]">
              JARVIS
            </div>
            <div className="eyebrow">multi-model core</div>
          </div>

          <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
            {TABS.map(({ id, label, icon: Icon }) => {
              const on = tab === id
              return (
                <button key={id} onClick={() => setTab(id)}
                  className={`relative w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium tracking-wide transition-colors ${
                    on ? 'text-core' : 'text-[#7FA3B2] hover:text-core/90'}`}>
                  {on && (
                    <motion.span layoutId="nav-active"
                      className="absolute inset-0 rounded-lg bg-core/10 border border-core/40 shadow-glow-sm"
                      transition={{ type: 'spring', stiffness: 420, damping: 34 }} />
                  )}
                  <span className={`absolute left-0 top-1/2 -translate-y-1/2 h-5 w-[3px] rounded-full transition-all ${
                    on ? 'bg-core shadow-glow' : 'bg-transparent'}`} />
                  <Icon size={17} className="relative z-10" />
                  <span className="relative z-10">{label}</span>
                </button>
              )
            })}
          </div>

          <div className="px-4 py-4 border-t border-core/10 space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_2px_rgba(52,211,153,0.7)] animate-pulse" />
              <span className="tag !text-emerald-300/80">online</span>
            </div>
            <div className="tag">model · <span className="text-core/70">{model}</span></div>
          </div>
        </nav>

        {/* ── workspace ───────────────────────────────────────── */}
        <main className="flex-1 min-w-0 flex flex-col">
          {/* top HUD bar */}
          <header className="shrink-0 h-16 px-6 flex items-center justify-between glass border-x-0 border-t-0">
            <div className="flex items-baseline gap-3">
              <h1 className="font-display text-base font-semibold tracking-[0.18em] uppercase text-[#DBF4FA]">
                {active.label}
              </h1>
              <span className="hidden sm:block tag">{active.blurb}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="tag">SYS</span>
              <span className="h-1.5 w-1.5 rounded-full bg-core animate-pulse" />
              <span className="tag text-core/70">nominal</span>
            </div>
          </header>

          {/* tab body */}
          <div key={tab} className="flex-1 min-h-0 animate-fade-up">
            {tab === 'chat' && <ChatTab model={model} />}
            {tab === 'voice' && <VoiceTab model={model} />}
            {tab === 'council' && <CouncilTab />}
            {tab === 'graph' && <GraphTab />}
            {tab === 'memory' && <MemoryTab />}
            {tab === 'tools' && <ToolsTab />}
            {tab === 'settings' && <SettingsTab model={model} setModel={setModel} />}
          </div>
        </main>
      </div>
    </div>
  )
}
