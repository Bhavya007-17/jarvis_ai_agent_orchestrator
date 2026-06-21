import { useEffect, useState } from 'react'
import { fetchModels } from '../lib/chatSocket'
import ProvidersPanel from './ProvidersPanel'

export default function SettingsTab({ model, setModel }) {
  const [models, setModels] = useState(['auto'])
  const [taskMap, setTaskMap] = useState({})

  const loadModels = () => fetchModels().then((d) => { setModels(d.models); setTaskMap(d.task_map) })
  useEffect(() => { loadModels() }, [])

  return (
    <div className="p-6 space-y-5 max-w-lg">
      <div>
        <div className="eyebrow">configuration</div>
        <h2 className="font-display text-lg uppercase tracking-[0.15em] text-[#DBF4FA]">Settings</h2>
      </div>
      <div className="glass rounded-xl p-4 space-y-2">
        <label className="block text-sm text-[#9FD8E4] tracking-wide">Chat model
          <select value={model} onChange={(e) => setModel(e.target.value)}
            className="hud-input mt-1.5 w-full px-3 py-2.5">
            {models.map((m) => <option key={m} value={m} className="bg-void">{m}</option>)}
          </select>
        </label>
        <p className="tag">“auto” routes by task type — switches live, no restart</p>
      </div>
      <ProvidersPanel onSaved={loadModels} />
      <div className="glass rounded-xl p-4">
        <div className="font-hud text-xs uppercase tracking-wider text-core/80 mb-2">per-task map</div>
        <ul className="space-y-1 text-sm">
          {Object.entries(taskMap).map(([k, v]) => (
            <li key={k} className="flex items-center gap-2">
              <span className="text-[#7FA3B2] capitalize w-24">{k}</span>
              <span className="text-core/50">→</span>
              <span className="font-hud text-[12px] text-[#DBF4FA] break-all">{v || '(unset)'}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
