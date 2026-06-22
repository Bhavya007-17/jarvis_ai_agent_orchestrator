// web/src/components/AuthLock.jsx
// Full-screen themed unlock overlay. Ported from _vendor/ada_v2/src/components/AuthLock.jsx
// but WS-free and re-themed to Jarvis HUD tokens: the browser captures the camera, extracts
// a face vector via the (injectable) recognizer, POSTs it to /api/vision/verify, and on a
// server-confirmed match plays the unlock animation then calls onUnlock().
import { useEffect, useRef, useState } from 'react'
import { Lock, Unlock, User } from 'lucide-react'
import { verify } from '../lib/visionApi'
import { createFaceMesh } from '../lib/faceMesh'

const POLL_MS = 333 // ~3 fps

export default function AuthLock({ onUnlock, recognizerFactory = createFaceMesh }) {
  const [message, setMessage] = useState('Look at the camera to unlock.')
  const [unlocking, setUnlocking] = useState(false)
  const videoRef = useRef(null)
  const unlockingRef = useRef(false)

  useEffect(() => {
    let stream
    let timer
    let mesh
    let cancelled = false

    async function run() {
      try {
        mesh = await recognizerFactory()
        stream = await navigator.mediaDevices.getUserMedia({ video: true })
        if (cancelled) return
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          await videoRef.current.play().catch(() => {})
        }
      } catch (e) {
        setMessage('Camera unavailable - cannot unlock.')
        return
      }
      const tick = async () => {
        if (cancelled || unlockingRef.current) return
        try {
          const vec = mesh.extract(videoRef.current)
          if (vec) {
            const res = await verify(Array.from(vec))
            if (res && res.match && !unlockingRef.current) {
              unlockingRef.current = true
              setUnlocking(true)
              setMessage('Identity verified. Access granted.')
              setTimeout(() => { if (!cancelled) onUnlock() }, 1200)
              return
            }
          }
        } catch { /* keep scanning */ }
        timer = setTimeout(tick, POLL_MS)
      }
      timer = setTimeout(tick, POLL_MS)
    }
    run()

    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
      if (stream) stream.getTracks().forEach((t) => t.stop())
    }
  }, [onUnlock, recognizerFactory])

  return (
    <div className={`fixed inset-0 z-[9999] flex flex-col items-center justify-center hud-field font-hud select-none transition-opacity duration-1000 ${unlocking ? 'opacity-0 pointer-events-none' : 'opacity-100'}`}
         style={{ transitionDelay: unlocking ? '900ms' : '0ms' }}>
      <div className="pointer-events-none absolute inset-x-0 top-0 scanline animate-scan opacity-40" />
      <div className="relative flex flex-col items-center gap-6 p-10 rounded-2xl glass">
        <div className={`flex items-center gap-4 text-2xl font-bold tracking-[0.3em] uppercase ${unlocking ? 'text-emerald-300' : 'text-core'}`}>
          {unlocking ? <Unlock size={28} /> : <Lock size={28} />}
          {unlocking ? 'SYSTEM UNLOCKED' : 'SYSTEM LOCKED'}
        </div>
        <div className="relative w-64 h-64 rounded-xl overflow-hidden glass flex items-center justify-center">
          <video ref={videoRef} muted playsInline
                 className="w-full h-full object-cover scale-x-[-1]" />
          {!unlocking && (
            <div className="absolute inset-x-0 top-0 scanline animate-scan" />
          )}
          {unlocking && (
            <div className="absolute inset-0 flex items-center justify-center bg-emerald-500/20">
              <Unlock size={56} className="text-emerald-300" />
            </div>
          )}
          <User size={48} className="absolute text-core/20 -z-10" />
        </div>
        <div className={`text-sm tracking-widest ${unlocking ? 'text-emerald-200' : 'text-core'}`}>
          {message}
        </div>
      </div>
    </div>
  )
}
