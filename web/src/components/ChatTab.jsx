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
      <div className="flex-1 overflow-y-auto space-y-3 p-6">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center gap-2">
            <div className="eyebrow">awaiting input</div>
            <p className="text-[#5B7A8A] text-sm max-w-xs">
              Ask anything. Your prompt is classified and routed to the best model, then tagged with the one that answered.
            </p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === 'you' ? 'text-right' : 'text-left'}>
            <div className={`inline-block px-4 py-2.5 rounded-2xl max-w-[80%] text-[15px] leading-relaxed ${
              m.role === 'you' ? 'bg-core/15 border border-core/40 text-[#DBF4FA] shadow-glow-sm'
                               : m.error ? 'bg-rose-950/40 border border-rose-600/40 text-rose-200'
                                         : 'glass text-[#CBE7F0]'}`}>
              <span className="whitespace-pre-wrap">{m.text || '…'}</span>
              {m.rung && <span className="block mt-1.5 tag">served by {m.rung}</span>}
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <div className="p-4 border-t border-core/10 flex gap-2">
        <input
          className="hud-input flex-1 px-4 py-2.5"
          placeholder="Ask Jarvis…" value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()} />
        <button onClick={send} disabled={busy} className="hud-btn px-4 py-2.5">
          <Send size={18} />
        </button>
      </div>
    </div>
  )
}
