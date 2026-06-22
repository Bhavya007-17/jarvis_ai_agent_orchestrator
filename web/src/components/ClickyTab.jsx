// web/src/components/ClickyTab.jsx
// Clicky module — "where is X on my screen?" The server captures the screen,
// a vision model locates the element via two-stage grid pointing, and we render
// the returned (already annotated) screenshot plus the answer.
import { useState } from 'react'
import { point } from '../lib/clickyApi'

export default function ClickyTab() {
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)

  async function ask() {
    const q = question.trim()
    if (!q || busy) return
    setBusy(true)
    setResult(null)
    const res = await point(q)
    setResult(res)
    setBusy(false)
  }

  return (
    <div className="flex h-full flex-col gap-3 p-3 text-sm text-cyan-100">
      <div className="flex gap-2">
        <input
          className="flex-1 rounded border border-cyan-500/30 bg-black/40 px-3 py-2 text-cyan-100 outline-none focus:border-cyan-400"
          placeholder="Where is the Save button?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && ask()}
          disabled={busy}
        />
        <button
          className="rounded border border-cyan-400/50 bg-cyan-500/10 px-4 py-2 font-medium text-cyan-200 hover:bg-cyan-500/20 disabled:opacity-40"
          onClick={ask}
          disabled={busy || !question.trim()}
        >
          {busy ? 'Looking…' : 'Locate'}
        </button>
      </div>

      {result && (
        <div className="flex min-h-0 flex-1 flex-col gap-2">
          <div className={result.found ? 'text-cyan-300' : 'text-amber-300'}>
            {result.description}
            {result.found && result.point && (
              <span className="ml-2 text-cyan-500/70">
                ({result.point[0]}, {result.point[1]})
              </span>
            )}
          </div>
          {result.screenshot_b64 ? (
            <div className="min-h-0 flex-1 overflow-auto rounded border border-cyan-500/20 bg-black/30">
              <img
                className="max-w-full"
                alt="screen capture with the located element highlighted"
                src={`data:image/jpeg;base64,${result.screenshot_b64}`}
              />
            </div>
          ) : null}
        </div>
      )}

      {!result && !busy && (
        <p className="text-cyan-500/60">
          Ask where something is on your screen. Jarvis captures the screen and a vision
          model highlights the element. Requires <code>VISION_MODEL</code> in <code>.env</code>.
        </p>
      )}
    </div>
  )
}
