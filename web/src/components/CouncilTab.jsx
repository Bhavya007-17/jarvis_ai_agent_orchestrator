import { useState } from 'react'
import { Play } from 'lucide-react'
import { openCouncil } from '../lib/api'

const kindOf = (label) =>
  label.startsWith('PROPOSAL') ? 'proposal'
    : label.startsWith('CRITIQUE') ? 'critique'
      : label.startsWith('SYNTH') ? 'synthesis' : 'executor'
const ACCENT = {
  proposal: 'border-cyan-700', critique: 'border-amber-600',
  synthesis: 'border-emerald-600', executor: 'border-slate-600',
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
      <div className="p-4 border-b border-slate-800 flex gap-2">
        <input className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-2 outline-none focus:border-cyan-500"
          placeholder="Planning task for the council…" value={task}
          onChange={(e) => setTask(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && run()} />
        <button onClick={run} disabled={busy}
          className="px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 flex items-center gap-1">
          <Play size={16} /> Convene
        </button>
      </div>
      <div className="text-xs text-slate-400 px-4 py-1">{status}</div>
      <div className="flex-1 overflow-y-auto grid grid-cols-1 md:grid-cols-3 gap-3 p-4 auto-rows-min">
        {voices.map((v, i) => (
          <div key={i} className={`rounded-xl border ${ACCENT[kindOf(v.label)]} bg-slate-900/60 p-3 ${kindOf(v.label) !== 'proposal' ? 'md:col-span-3' : ''}`}>
            <div className="text-xs font-semibold text-slate-300 flex justify-between gap-2">
              <span>{v.label}</span>{v.done && <span className="text-slate-500 truncate">✓ {v.model}</span>}
            </div>
            <div className="mt-2 text-sm whitespace-pre-wrap text-slate-200">{v.text || '…'}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
