import { useState, useRef, useEffect } from 'react'
import { Send } from 'lucide-react'
import { sendChat } from '../lib/chatSocket'

export default function ChatTab({ model }) {
  const [messages, setMessages] = useState([])  // {role, text, rung?}
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const endRef = useRef(null)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const send = () => {
    const text = input.trim()
    if (!text || busy) return
    setInput('')
    setBusy(true)
    setMessages((m) => [...m, { role: 'you', text }, { role: 'jarvis', text: '', rung: null }])
    sendChat({
      message: text,
      model,
      onFrame: (f) => {
        if (f.type === 'rung') {
          setMessages((m) => m.map((msg, i) => i === m.length - 1 ? { ...msg, rung: f.rung } : msg))
        } else if (f.type === 'chunk') {
          setMessages((m) => m.map((msg, i) => i === m.length - 1 ? { ...msg, text: msg.text + f.content } : msg))
        } else if (f.type === 'error') {
          setMessages((m) => m.map((msg, i) => i === m.length - 1 ? { ...msg, text: `⚠ ${f.detail}`, error: true } : msg))
        }
      },
      onClose: () => setBusy(false),
    })
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto space-y-3 p-4">
        {messages.map((m, i) => (
          <div key={i} className={m.role === 'you' ? 'text-right' : 'text-left'}>
            <div className={`inline-block px-3 py-2 rounded-2xl max-w-[80%] ${
              m.role === 'you' ? 'bg-cyan-600/30 border border-cyan-500/40'
                               : m.error ? 'bg-red-900/30 border border-red-600/40'
                                         : 'bg-slate-800/70 border border-slate-700'}`}>
              <span className="whitespace-pre-wrap">{m.text || '…'}</span>
              {m.rung && <span className="block mt-1 text-[10px] text-slate-400">served by {m.rung}</span>}
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <div className="p-4 border-t border-slate-800 flex gap-2">
        <input
          className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-2 outline-none focus:border-cyan-500"
          placeholder="Ask Jarvis…" value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()} />
        <button onClick={send} disabled={busy}
          className="px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40">
          <Send size={18} />
        </button>
      </div>
    </div>
  )
}
