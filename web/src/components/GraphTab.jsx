import { useEffect, useState } from 'react'
import { getJSON, GRAPH_URL } from '../lib/api'

export default function GraphTab() {
  const [routing, setRouting] = useState(null)
  useEffect(() => { getJSON('/api/routing').then(setRouting) }, [])

  return (
    <div className="flex h-full">
      <div className="flex-1 min-w-0">
        <iframe title="code-graph" src={GRAPH_URL} className="w-full h-full border-0 bg-slate-900" />
      </div>
      <aside className="w-72 border-l border-slate-800 p-4 overflow-y-auto">
        <h3 className="text-cyan-300 text-sm font-semibold">Routing map</h3>
        {!routing || routing.error ? (
          <p className="text-xs text-slate-500 mt-2">routing unavailable (sidecar offline?)</p>
        ) : (
          <div className="mt-3 space-y-3 text-xs">
            {Object.entries(routing.ladders || {}).map(([tt, rungs]) => (
              <div key={tt}>
                <div className="text-slate-300 font-medium capitalize">{tt}</div>
                <div className="text-slate-400">{rungs.map((r) => r.label).join(' → ')}</div>
                <div className="text-slate-500 text-[10px] break-all">{rungs[0]?.model}</div>
              </div>
            ))}
            <a href={routing.graph_url} target="_blank" rel="noreferrer" className="text-cyan-400 underline block pt-2">open graph :9749 ↗</a>
          </div>
        )}
      </aside>
    </div>
  )
}
