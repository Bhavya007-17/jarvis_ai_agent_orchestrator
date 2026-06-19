const WS_URL = 'ws://localhost:8700/api/voice'
const FRAME_SAMPLES = 1280 // ~80 ms @ 16 kHz

/**
 * Open the always-on voice socket and start streaming mic PCM.
 * @returns {Promise<{stop: () => void, cancel: () => void, ws: WebSocket}>}
 */
export async function startVoice({ model, voice, onFrame, onAudio, onLevel, onError }) {
  const ws = new WebSocket(WS_URL)
  ws.binaryType = 'arraybuffer'

  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
  })
  const ctx = new AudioContext({ sampleRate: 16000 })
  await ctx.audioWorklet.addModule('/pcm-worklet.js')
  const src = ctx.createMediaStreamSource(stream)
  const node = new AudioWorkletNode(ctx, 'pcm-worklet')

  let batch = []
  let batchLen = 0
  node.port.onmessage = (e) => {
    const block = new Int16Array(e.data)
    batch.push(block)
    batchLen += block.length
    if (batchLen >= FRAME_SAMPLES) {
      const merged = new Int16Array(batchLen)
      let off = 0
      for (const b of batch) { merged.set(b, off); off += b.length }
      batch = []
      batchLen = 0
      if (onLevel) {
        let sum = 0
        for (let i = 0; i < merged.length; i++) sum += merged[i] * merged[i]
        onLevel(Math.sqrt(sum / merged.length))
      }
      if (ws.readyState === WebSocket.OPEN) ws.send(merged.buffer)
    }
  }
  src.connect(node)

  ws.onopen = () => ws.send(JSON.stringify({ model, voice }))
  ws.onmessage = (e) => {
    if (typeof e.data === 'string') {
      try { onFrame(JSON.parse(e.data)) } catch { /* ignore malformed frame */ }
    } else {
      onAudio(e.data)
    }
  }
  ws.onerror = () => onError && onError()

  const teardown = () => {
    try { src.disconnect() } catch { /* noop */ }
    try { node.disconnect() } catch { /* noop */ }
    try { ctx.close() } catch { /* noop */ }
    stream.getTracks().forEach((t) => t.stop())
  }
  return {
    stop() { try { ws.close() } catch { /* noop */ } teardown() },
    cancel() { if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'cancel' })) },
    ws,
  }
}
