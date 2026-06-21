import { useState } from 'react'
import { Play } from 'lucide-react'
import { openCouncil } from '../lib/api'

const kindOf = (label) =>
  label.startsWith('PROPOSAL') ? 'proposal'
    : label.startsWith('CRITIQUE') ? 'critique'
      : label.startsWith('SYNTH') ? 'synthesis' : 'executor'
const ACCENT = {
  proposal: 'border-core/40', critique: 'border-amber-500/50',
  synthesis: 'border-emerald-500/50', executor: 'border-core/15',
}
const DOT = {
  proposal: 'bg-core', critique: 'bg-amber-400',
  synthesis: 'bg-emerald-400', executor: 'bg-[#5B7A8A]',
}

export default function CouncilTab() {
  const [task, setTask] = useState('')
  const [voices, setVoices] = useState([])
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')

  const run = () => {
    const t = task.trim()
    if (!t || busy) return
    setVoices([]); setBusy(true); setStatus('convening…')
    openCouncil({
      task: t, execute: false,
      onFrame: (f) => {
        if (f.type === 'voice_start') {
          setVoices((v) => [...v, { label: f.label, model: f.model, text: '', done: false }])
        } else if (f.type === 'voice_chunk') {
          setVoices((v) => v.map((x) => x.label === f.label && !x.done ? { ...x, text: x.text + f.content } : x))
        } else if (f.type === 'voice_end') {
          setVoices((v) => v.map((x) => x.label === f.label ? { ...x, done: true, model: f.model || x.model } : x))
        } else if (f.type === 'council_done') {
          setStatus(`done — ${f.voices?.length || 0} voices`)
        } else if (f.type === 'error') {
          setStatus(`error: ${f.detail}`)
        }
      },
      onClose: () => setBusy(false),
    })
  }

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-core/10 flex gap-2">
        <input className="hud-input flex-1 px-4 py-2.5"
          placeholder="Planning task for the council…" value={task}
          onChange={(e) => setTask(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && run()} />
        <button onClick={run} disabled={busy} className="hud-btn px-4 py-2.5">
          <Play size={16} /> Convene
        </button>
      </div>
      {status && <div className="tag px-4 py-1.5">{status}</div>}
      <div className="flex-1 overflow-y-auto grid grid-cols-1 md:grid-cols-3 gap-3 p-4 auto-rows-min">
        {voices.length === 0 && !busy && (
          <div className="md:col-span-3 h-full flex flex-col items-center justify-center text-center gap-2 py-16">
            <div className="eyebrow">council standby</div>
            <p className="text-[#5B7A8A] text-sm max-w-sm">
              Pose a hard planning task. Three distinct models propose in parallel, a reasoning model critiques, then synthesizes one plan.
            </p>
          </div>
        )}
        {voices.map((v, i) => {
          const kind = kindOf(v.label)
          return (
            <div key={i} className={`rounded-xl border glass ${ACCENT[kind]} p-4 animate-fade-up ${kind !== 'proposal' ? 'md:col-span-3' : ''}`}>
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full ${DOT[kind]} ${!v.done ? 'animate-pulse' : ''}`} />
                  <span className="font-hud text-xs uppercase tracking-wider text-[#9FD8E4]">{v.label}</span>
                </div>
                {v.done && <span className="tag truncate">✓ {v.model}</span>}
              </div>
              <div className="mt-2.5 text-sm leading-relaxed whitespace-pre-wrap text-[#CBE7F0]">{v.text || '…'}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
