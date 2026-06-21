import { useEffect, useState } from 'react'
import { getJSON, GRAPH_URL } from '../lib/api'

export default function GraphTab() {
  const [routing, setRouting] = useState(null)
  useEffect(() => { getJSON('/api/routing').then(setRouting) }, [])

  return (
    <div className="flex h-full">
      <div className="flex-1 min-w-0 relative">
        <iframe title="code-graph" src={GRAPH_URL} className="w-full h-full border-0 bg-void" />
      </div>
      <aside className="w-80 shrink-0 glass border-y-0 border-r-0 p-5 overflow-y-auto">
        <div className="eyebrow">routing map</div>
        <h3 className="font-display text-sm uppercase tracking-[0.15em] text-[#DBF4FA] mt-1">Fallback ladders</h3>
        {!routing || routing.error ? (
          <p className="text-xs text-[#5B7A8A] mt-3">routing unavailable (sidecar offline?)</p>
        ) : (
          <div className="mt-4 space-y-3 text-xs">
            {Object.entries(routing.ladders || {}).map(([tt, rungs]) => (
              <div key={tt} className="rounded-lg glass p-3">
                <div className="text-core font-semibold capitalize tracking-wide text-sm">{tt}</div>
                <div className="font-hud text-[#9FD8E4] mt-1 text-[11px]">{rungs.map((r) => r.label).join('  →  ')}</div>
                <div className="tag break-all mt-1">{rungs[0]?.model}</div>
              </div>
            ))}
            <a href={routing.graph_url} target="_blank" rel="noreferrer"
              className="hud-btn-ghost w-full justify-center px-3 py-2 mt-2">open graph :9749 ↗</a>
          </div>
        )}
      </aside>
    </div>
  )
}
