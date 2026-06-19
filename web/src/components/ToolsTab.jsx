import { useEffect, useState } from 'react'
import { Plus, RefreshCw } from 'lucide-react'
import { getJSON, postJSON } from '../lib/api'

export default function ToolsTab() {
  const [servers, setServers] = useState([])
  const [tools, setTools] = useState(null)
  const [discovering, setDiscovering] = useState(false)
  const [form, setForm] = useState({ name: '', command: '', args: '' })
  const [msg, setMsg] = useState('')

  const refresh = () => getJSON('/api/mcp/servers').then((d) => { if (!d.error) setServers(d.servers || []) })
  useEffect(() => { refresh() }, [])

  const add = async () => {
    if (!form.name.trim() || !form.command.trim()) return
    const args = form.args.trim() ? form.args.split(/\s+/) : []
    const r = await postJSON('/api/mcp/servers', { name: form.name, command: form.command, args })
    setMsg(r.message || '')
    if (r.servers) setServers(r.servers)
    setForm({ name: '', command: '', args: '' })
  }
  const discover = async () => {
    setDiscovering(true); setTools(null)
    const r = await getJSON('/api/mcp/tools')
    setTools(r.tools || [])
    setMsg(r.ok ? `${(r.tools || []).length} tools discovered` : `discovery: ${r.detail || 'failed'}`)
    setDiscovering(false)
  }

  return (
    <div className="p-6 space-y-5 overflow-y-auto h-full">
      <h2 className="text-lg text-cyan-300">Tools — MCP servers</h2>
      <ul className="space-y-1">
        {servers.length ? servers.map((s) => (
          <li key={s.name} className="bg-slate-900/60 border border-slate-800 rounded-lg px-3 py-2 text-sm">
            <span className="text-slate-200 font-medium">{s.name}</span>
            <span className="text-slate-500 text-xs break-all"> — {s.command} {(s.args || []).join(' ')}</span>
          </li>
        )) : <li className="text-xs text-slate-500">no MCP servers configured (run setup_config.py)</li>}
      </ul>
      <div className="flex flex-wrap gap-2 items-end">
        <input placeholder="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
          className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm w-32" />
        <input placeholder="command" value={form.command} onChange={(e) => setForm({ ...form, command: e.target.value })}
          className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm flex-1 min-w-40" />
        <input placeholder="args (space-sep)" value={form.args} onChange={(e) => setForm({ ...form, args: e.target.value })}
          className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm w-40" />
        <button onClick={add} className="px-3 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 flex items-center gap-1 text-sm"><Plus size={14} /> Add server</button>
      </div>
      <div>
        <button onClick={discover} disabled={discovering}
          className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 flex items-center gap-1 text-sm">
          <RefreshCw size={14} className={discovering ? 'animate-spin' : ''} /> Discover tools
        </button>
        {tools && <ul className="mt-2 grid grid-cols-2 gap-1 text-xs text-slate-400">{tools.map((t) => <li key={t}>• {t}</li>)}</ul>}
      </div>
      {msg && <div className="text-xs text-slate-400">{msg}</div>}
    </div>
  )
}
