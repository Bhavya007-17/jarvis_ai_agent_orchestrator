import { useEffect, useState } from 'react'
import { fetchModels } from '../lib/chatSocket'

export default function SettingsTab({ model, setModel }) {
  const [models, setModels] = useState(['auto'])
  const [taskMap, setTaskMap] = useState({})

  useEffect(() => { fetchModels().then((d) => { setModels(d.models); setTaskMap(d.task_map) }) }, [])

  return (
    <div className="p-6 space-y-4 max-w-lg">
      <h2 className="text-lg text-cyan-300">Settings</h2>
      <label className="block text-sm text-slate-300">Chat model
        <select value={model} onChange={(e) => setModel(e.target.value)}
          className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2">
          {models.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
      </label>
      <p className="text-xs text-slate-400">"auto" routes by task type. Per-task map:</p>
      <ul className="text-xs text-slate-400">
        {Object.entries(taskMap).map(([k, v]) => <li key={k}>{k} → {v || '(unset)'}</li>)}
      </ul>
    </div>
  )
}
