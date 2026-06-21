// web/src/components/VoiceTab.jsx
import { useEffect, useRef, useState } from 'react'
import { Mic, MicOff } from 'lucide-react'
import { startVoice } from '../lib/voiceSocket'

const BARGE_RMS = 1800 // mic RMS that counts as "talking over" the assistant

export default function VoiceTab({ model = 'auto' }) {
  const [on, setOn] = useState(false)
  const [status, setStatus] = useState('off') // off|sleeping|listening|thinking|speaking
  const [log, setLog] = useState([])           // {role:'you'|'jarvis', text}
  const [error, setError] = useState('')

  const ctrlRef = useRef(null)
  const queueRef = useRef([])      // pending mp3 ArrayBuffers
  const audioRef = useRef(null)    // current HTMLAudioElement
  const playingRef = useRef(false)

  const append = (role, text) =>
    setLog((l) => [...l.slice(-30), { role, text }])

  const stopPlayback = () => {
    queueRef.current = []
    if (audioRef.current) { audioRef.current.pause(); audioRef.current = null }
    playingRef.current = false
  }

  const playNext = () => {
    if (playingRef.current) return
    const buf = queueRef.current.shift()
    if (!buf) { if (status === 'speaking') setStatus('listening'); return }
    playingRef.current = true
    setStatus('speaking')
    const url = URL.createObjectURL(new Blob([buf], { type: 'audio/mpeg' }))
    const audio = new Audio(url)
    audioRef.current = audio
    audio.onended = () => {
      URL.revokeObjectURL(url)
      playingRef.current = false
      audioRef.current = null
      playNext()
    }
    audio.play().catch(() => { playingRef.current = false })
  }

  const onFrame = (f) => {
    if (f.type === 'wake') { setStatus('listening'); append('jarvis', '(awake — listening)') }
    else if (f.type === 'sleep') { setStatus('sleeping'); stopPlayback() }
    else if (f.type === 'transcript') { append('you', f.text); setStatus('thinking') }
    else if (f.type === 'answer') { append('jarvis', f.content) }
    else if (f.type === 'turn_end') {
      // Explicit turn-completion signal from server. If no audio is playing or
      // queued, flip back to listening immediately; otherwise let playNext()'s
      // 'ended' chain handle it once the queue empties.
      if (!playingRef.current && queueRef.current.length === 0) setStatus('listening')
    }
    else if (f.type === 'error') { setError(f.detail || 'error') }
  }

  const onAudio = (buf) => { queueRef.current.push(buf); playNext() }

  const onLevel = (rms) => {
    // Barge-in: user talks over the assistant -> stop playback immediately.
    if (playingRef.current && rms > BARGE_RMS) {
      stopPlayback()
      ctrlRef.current && ctrlRef.current.cancel()
      setStatus('listening')
    }
  }

  const start = async () => {
    setError('')
    try {
      ctrlRef.current = await startVoice({
        model, voice: undefined, onFrame, onAudio, onLevel,
        onError: () => setError('voice socket error'),
      })
      setOn(true)
      setStatus('sleeping')
    } catch (e) {
      setError(`mic/socket failed: ${e && e.message ? e.message : e}`)
    }
  }

  const stop = () => {
    stopPlayback()
    ctrlRef.current && ctrlRef.current.stop()
    ctrlRef.current = null
    setOn(false)
    setStatus('off')
  }

  useEffect(() => () => { ctrlRef.current && ctrlRef.current.stop() }, [])

  const live = on && status !== 'off'
  return (
    <div className="h-full flex flex-col p-6 gap-4">
      <div className="flex items-center gap-4">
        <button
          onClick={on ? stop : start}
          className={on ? 'hud-btn-ghost px-4 py-2.5 !text-rose-300 !border-rose-500/40' : 'hud-btn px-4 py-2.5'}>
          {on ? <MicOff size={16} /> : <Mic size={16} />}
          {on ? 'Stop' : 'Start always-on'}
        </button>
        <div className="flex items-center gap-2">
          <span className={`h-2.5 w-2.5 rounded-full ${live ? 'bg-core shadow-glow animate-pulse' : 'bg-[#2A3D47]'}`} />
          <span className="tag">status</span>
          <span className="font-hud text-sm text-core uppercase tracking-wider">{status}</span>
          {status === 'sleeping' && <span className="tag">— say “Hey Jarvis”</span>}
        </div>
      </div>
      {error && <div className="text-rose-400 text-sm">{error}</div>}
      <div className="flex-1 min-h-0 overflow-auto space-y-2.5 rounded-xl glass p-5">
        {log.length === 0 && <div className="text-[#5B7A8A] text-sm">
          Start always-on, then say “Hey Jarvis” and speak. Talk over Jarvis to interrupt.
        </div>}
        {log.map((m, i) => (
          <div key={i} className={m.role === 'you' ? 'text-[#DBF4FA]' : 'text-core'}>
            <span className="tag mr-2">{m.role}</span>{m.text}
          </div>
        ))}
      </div>
    </div>
  )
}
