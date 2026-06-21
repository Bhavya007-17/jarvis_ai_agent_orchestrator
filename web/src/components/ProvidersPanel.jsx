import { useEffect, useState } from 'react'
import { fetchProviders, saveProviderKey, PROVIDER_LABELS } from '../lib/providers'

// Phase 7 — paste a provider key, its models go live everywhere with no
// restart. The input is masked and cleared on save; the UI only ever sees a
// green/grey "configured" dot driven by presence booleans (never the key).
export default function ProvidersPanel({ onSaved }) {
  const [present, setPresent] = useState({})
  const [known, setKnown] = useState([])
  const [drafts, setDrafts] = useState({})   // per-provider input text
  const [busy, setBusy] = useState('')        // provider currently saving
  const [note, setNote] = useState(null)      // { provider, ok, message }

  const refresh = () => fetchProviders().then((d) => {
    setPresent(d.providers || {})
    setKnown(d.known || [])
  })
  useEffect(() => { refresh() }, [])

  async function save(provider) {
    const key = (drafts[provider] || '').trim()
    if (!key) return
    setBusy(provider)
    const res = await saveProviderKey(provider, key)
    setBusy('')
    setNote({ provider, ok: !!res.ok, message: res.message || (res.ok ? 'Saved' : 'Failed') })
    if (res.ok) {
      setDrafts((d) => ({ ...d, [provider]: '' }))  // never linger the secret
      setPresent(res.providers || present)
      onSaved && onSaved()                          // let Settings refresh models
    }
  }

  return (
    <div className="glass rounded-xl p-4 space-y-3">
      <div className="font-hud text-xs uppercase tracking-wider text-core/80">
        provider keys
      </div>
      <p className="tag">Paste a key — its models become selectable instantly. Keys live in .env and are never shown back.</p>
      <div className="space-y-2.5">
        {known.map((p) => (
          <div key={p} className="flex items-center gap-2">
            <span
              title={present[p] ? 'configured' : 'not configured'}
              className={`h-2.5 w-2.5 rounded-full shrink-0 ${present[p]
                ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]'
                : 'bg-white/20'}`}
            />
            <span className="text-sm text-[#9FD8E4] w-40 shrink-0">{PROVIDER_LABELS[p] || p}</span>
            <input
              type="password"
              autoComplete="off"
              placeholder={present[p] ? '•••••••• (replace)' : 'paste key'}
              value={drafts[p] || ''}
              onChange={(e) => setDrafts((d) => ({ ...d, [p]: e.target.value }))}
              onKeyDown={(e) => { if (e.key === 'Enter') save(p) }}
              className="hud-input flex-1 px-3 py-2 text-sm"
            />
            <button
              onClick={() => save(p)}
              disabled={busy === p || !(drafts[p] || '').trim()}
              className="hud-input px-3 py-2 text-xs uppercase tracking-wider disabled:opacity-40"
            >
              {busy === p ? '…' : 'Save'}
            </button>
          </div>
        ))}
      </div>
      {note && (
        <p className={`text-xs ${note.ok ? 'text-emerald-300' : 'text-rose-300'}`}>
          {PROVIDER_LABELS[note.provider] || note.provider}: {note.message}
        </p>
      )}
    </div>
  )
}
