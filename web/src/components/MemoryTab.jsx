import { useEffect, useState } from 'react'
import { Trash2, Plus } from 'lucide-react'
import { getJSON, postJSON, delJSON } from '../lib/api'

export default function MemoryTab() {
  const [data, setData] = useState({ facts: {}, categories: [] })
  const [form, setForm] = useState({ key: '', value: '', category: 'identity' })
  const [msg, setMsg] = useState('')

  const refresh = () => getJSON('/api/memory/facts').then((d) => { if (!d.error) setData(d) })
  useEffect(() => { refresh() }, [])

  const add = async () => {
    if (!form.key.trim() || !form.value.trim()) return
    const r = await postJSON('/api/memory/facts', form)
    setMsg(r.message || '')
    setForm({ ...form, key: '', value: '' })
    if (r.facts) setData((d) => ({ ...d, facts: r.facts }))
  }
  const forget = async (key, category) => {
    const r = await delJSON(`/api/memory/facts?key=${encodeURIComponent(key)}&category=${category}`)
    setMsg(r.message || '')
    if (r.facts) setData((d) => ({ ...d, facts: r.facts }))
  }

  const cats = data.categories.length ? data.categories : ['identity']
  return (
    <div className="p-6 space-y-5 overflow-y-auto h-full">
      <div>
        <div className="eyebrow">long-term store</div>
        <h2 className="font-display text-lg uppercase tracking-[0.15em] text-[#DBF4FA]">Personal facts</h2>
      </div>
      <div className="flex flex-wrap gap-2 items-end glass rounded-xl p-4">
        <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}
          className="hud-input px-2 py-2 text-sm">
          {cats.map((c) => <option key={c} value={c} className="bg-void">{c}</option>)}
        </select>
        <input placeholder="key" value={form.key} onChange={(e) => setForm({ ...form, key: e.target.value })}
          className="hud-input px-3 py-2 text-sm w-32" />
        <input placeholder="value" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })}
          className="hud-input px-3 py-2 text-sm flex-1 min-w-40" />
        <button onClick={add} className="hud-btn px-3 py-2 text-sm"><Plus size={14} /> Remember</button>
      </div>
      {msg && <div className="tag">{msg}</div>}
      <div className="space-y-4">
        {Object.entries(data.facts).map(([cat, items]) => Object.keys(items || {}).length ? (
          <div key={cat}>
            <div className="font-hud text-xs uppercase tracking-wider text-core/80">{cat}</div>
            <ul className="mt-1.5 space-y-1.5">
              {Object.entries(items).map(([k, entry]) => (
                <li key={k} className="flex items-center justify-between glass rounded-lg px-3 py-2 text-sm">
                  <span><span className="text-[#7FA3B2]">{k.replace(/_/g, ' ')}:</span> <span className="text-[#DBF4FA]">{entry.value}</span></span>
                  <button onClick={() => forget(k, cat)} className="text-[#5B7A8A] hover:text-rose-400 transition-colors"><Trash2 size={14} /></button>
                </li>
              ))}
            </ul>
          </div>
        ) : null)}
      </div>
    </div>
  )
}
