// web/src/components/VisionTab.jsx
// The Vision module: camera preview + enroll + face-lock toggle + gesture control +
// mic visualizer. Browser-side MediaPipe extraction; only enroll/verify hit the server.
import { useEffect, useRef, useState } from 'react'
import { ScanFace, Hand, Lock, Unlock } from 'lucide-react'
import { getStatus, enroll, setLock } from '../lib/visionApi'
import { createFaceMesh } from '../lib/faceMesh'
import { createHandTracker } from '../lib/handGestures'
import Visualizer from './Visualizer'

const GESTURE_DEBOUNCE_MS = 1500

export default function VisionTab({ onGestureAction }) {
  const [status, setStatus] = useState({ enrolled: false, lock_enabled: false })
  const [msg, setMsg] = useState('')
  const [gesture, setGesture] = useState('None')
  const [gestureOn, setGestureOn] = useState(false)
  const [intensity, setIntensity] = useState(0)

  const videoRef = useRef(null)
  const meshRef = useRef(null)
  const handRef = useRef(null)
  const lastFired = useRef(0)
  const lastGesture = useRef('None')

  const fakes = typeof window !== 'undefined' ? window.__VISION_FAKE__ : null
  const faceFactory = (fakes && fakes.faceFactory) || createFaceMesh
  const handFactory = (fakes && fakes.handFactory) || createHandTracker

  // Camera + mic preview + visualizer intensity.
  useEffect(() => {
    let stream, audioCtx, raf
    async function run() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
        if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play().catch(() => {}) }
        const aTrack = stream.getAudioTracks()
        if (aTrack.length) {
          audioCtx = new AudioContext()
          const src = audioCtx.createMediaStreamSource(stream)
          const analyser = audioCtx.createAnalyser()
          analyser.fftSize = 256
          src.connect(analyser)
          const buf = new Uint8Array(analyser.frequencyBinCount)
          const loop = () => {
            analyser.getByteFrequencyData(buf)
            let sum = 0
            for (let i = 0; i < buf.length; i++) sum += buf[i]
            setIntensity(Math.min(1, sum / buf.length / 128))
            raf = requestAnimationFrame(loop)
          }
          loop()
        }
      } catch { setMsg('Camera/mic unavailable.') }
    }
    run()
    getStatus().then(setStatus)
    return () => {
      if (raf) cancelAnimationFrame(raf)
      if (audioCtx) audioCtx.close().catch(() => {})
      if (stream) stream.getTracks().forEach((t) => t.stop())
    }
  }, [])

  // Gesture loop (only when enabled).
  useEffect(() => {
    if (!gestureOn) return
    let timer, cancelled = false
    async function start() {
      try { handRef.current = await handFactory() } catch { setMsg('Hand tracker failed to load.'); return }
      const tick = () => {
        if (cancelled) return
        let g = 'None'
        try { g = handRef.current.detect(videoRef.current) } catch { /* ignore */ }
        setGesture(g)
        const now = Date.now()
        if (g !== 'None' && g !== lastGesture.current && now - lastFired.current > GESTURE_DEBOUNCE_MS) {
          lastFired.current = now
          onGestureAction && onGestureAction(g)
        }
        lastGesture.current = g
        timer = setTimeout(tick, 200)
      }
      tick()
    }
    start()
    return () => { cancelled = true; if (timer) clearTimeout(timer) }
  }, [gestureOn, onGestureAction, handFactory])

  const doEnroll = async () => {
    try {
      if (!meshRef.current) meshRef.current = await faceFactory()
      const vec = meshRef.current.extract(videoRef.current)
      if (!vec) { setMsg('No face detected - center your face and retry.'); return }
      const res = await enroll(Array.from(vec))
      setMsg(res && res.ok ? 'Face enrolled.' : `Enroll failed: ${res && res.message}`)
      getStatus().then(setStatus)
    } catch (e) { setMsg(`Enroll error: ${e && e.message ? e.message : e}`) }
  }

  const toggleLock = async () => {
    const next = !status.lock_enabled
    await setLock(next)
    getStatus().then(setStatus)
  }

  return (
    <div className="h-full flex flex-col p-5 gap-4 overflow-auto">
      <div className="relative w-full aspect-video rounded-xl overflow-hidden glass">
        <video ref={videoRef} muted playsInline className="w-full h-full object-cover scale-x-[-1]" />
        <div className="absolute bottom-2 left-2 tag">{gesture}</div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button onClick={doEnroll} className="hud-btn px-4 py-2.5"><ScanFace size={16} /> Enroll face</button>
        <button onClick={toggleLock} className="hud-btn-ghost px-4 py-2.5">
          {status.lock_enabled ? <Lock size={16} /> : <Unlock size={16} />}
          {status.lock_enabled ? 'Face-lock ON' : 'Face-lock OFF'}
        </button>
        <button onClick={() => setGestureOn((v) => !v)}
                className={gestureOn ? 'hud-btn px-4 py-2.5' : 'hud-btn-ghost px-4 py-2.5'}>
          <Hand size={16} /> {gestureOn ? 'Gesture control ON' : 'Enable gesture control'}
        </button>
        <span className="tag">{status.enrolled ? 'enrolled' : 'not enrolled'}</span>
      </div>

      {msg && <div className="text-sm text-core">{msg}</div>}

      <div className="flex-1 min-h-0 flex items-center justify-center overflow-hidden pointer-events-none">
        <Visualizer isListening={gestureOn} intensity={intensity} width={360} height={220} />
      </div>
    </div>
  )
}
