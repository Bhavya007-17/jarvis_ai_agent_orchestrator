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
      <h2 className="text-lg text-cyan-300">Memory — personal facts</h2>
      <div className="flex flex-wrap gap-2 items-end">
        <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}
          className="bg-slate-900 border border-slate-700 rounded-lg px-2 py-2 text-sm">
          {cats.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <input placeholder="key" value={form.key} onChange={(e) => setForm({ ...form, key: e.target.value })}
          className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm w-32" />
        <input placeholder="value" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })}
          className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm flex-1 min-w-40" />
        <button onClick={add} className="px-3 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 flex items-center gap-1 text-sm"><Plus size={14} /> Remember</button>
      </div>
      {msg && <div className="text-xs text-slate-400">{msg}</div>}
      <div className="space-y-4">
        {Object.entries(data.facts).map(([cat, items]) => Object.keys(items || {}).length ? (
          <div key={cat}>
            <div className="text-sm text-slate-300 font-medium capitalize">{cat}</div>
            <ul className="mt-1 space-y-1">
              {Object.entries(items).map(([k, entry]) => (
                <li key={k} className="flex items-center justify-between bg-slate-900/60 border border-slate-800 rounded-lg px-3 py-1.5 text-sm">
                  <span><span className="text-slate-400">{k.replace(/_/g, ' ')}:</span> {entry.value}</span>
                  <button onClick={() => forget(k, cat)} className="text-slate-500 hover:text-red-400"><Trash2 size={14} /></button>
                </li>
              ))}
            </ul>
          </div>
        ) : null)}
      </div>
    </div>
  )
}
