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
      <div>
        <div className="eyebrow">model context protocol</div>
        <h2 className="font-display text-lg uppercase tracking-[0.15em] text-[#DBF4FA]">MCP servers</h2>
      </div>
      <ul className="space-y-1.5">
        {servers.length ? servers.map((s) => (
          <li key={s.name} className="glass rounded-lg px-3 py-2 text-sm flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_6px_1px_rgba(52,211,153,0.6)]" />
            <span className="text-[#DBF4FA] font-medium">{s.name}</span>
            <span className="tag break-all"> — {s.command} {(s.args || []).join(' ')}</span>
          </li>
        )) : <li className="tag">no MCP servers configured (run setup_config.py)</li>}
      </ul>
      <div className="flex flex-wrap gap-2 items-end glass rounded-xl p-4">
        <input placeholder="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
          className="hud-input px-3 py-2 text-sm w-32" />
        <input placeholder="command" value={form.command} onChange={(e) => setForm({ ...form, command: e.target.value })}
          className="hud-input px-3 py-2 text-sm flex-1 min-w-40" />
        <input placeholder="args (space-sep)" value={form.args} onChange={(e) => setForm({ ...form, args: e.target.value })}
          className="hud-input px-3 py-2 text-sm w-40" />
        <button onClick={add} className="hud-btn px-3 py-2 text-sm"><Plus size={14} /> Add server</button>
      </div>
      <div>
        <button onClick={discover} disabled={discovering} className="hud-btn-ghost px-3 py-2 text-sm disabled:opacity-40">
          <RefreshCw size={14} className={discovering ? 'animate-spin' : ''} /> Discover tools
        </button>
        {tools && <ul className="mt-3 grid grid-cols-2 gap-1.5 text-xs text-[#9FD8E4]">{tools.map((t) => <li key={t} className="font-hud">› {t}</li>)}</ul>}
      </div>
      {msg && <div className="tag">{msg}</div>}
    </div>
  )
}
