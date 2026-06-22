// web/src/lib/handGestures.js
// Hand-gesture classifier ported from _vendor/ada_v2/hand_gesture_test.py:48-81.
// Pure geometry over 21 normalized landmarks ({x,y,z}); no dependency, fully testable.
import { FilesetResolver, HandLandmarker } from '@mediapipe/tasks-vision'

function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y)
}

export function classifyGesture(lm) {
  if (!lm || lm.length < 21) return 'None'
  const indexExt = lm[8].y < lm[6].y
  const middleExt = lm[12].y < lm[10].y
  const ringExt = lm[16].y < lm[14].y
  const pinkyExt = lm[20].y < lm[18].y

  let gesture = 'None'
  if (indexExt && middleExt && ringExt && pinkyExt) gesture = 'Open Palm'
  else if (!indexExt && !middleExt && !ringExt && !pinkyExt) gesture = 'Closed Fist'
  else if (indexExt && !middleExt && !ringExt && !pinkyExt) {
    const dx = lm[8].x - lm[5].x
    const dy = lm[8].y - lm[5].y
    if (Math.abs(dy) > Math.abs(dx)) gesture = dy < 0 ? 'Point Up' : 'Point Down'
    else gesture = dx > 0 ? 'Point Right' : 'Point Left'
  } else if (indexExt && middleExt && !ringExt && !pinkyExt) gesture = 'Peace Sign'

  if (distance(lm[4], lm[8]) < 0.05) gesture = 'Pinching'
  return gesture
}

export async function createHandTracker() {
  const fileset = await FilesetResolver.forVisionTasks('/mediapipe/wasm')
  const tracker = await HandLandmarker.createFromOptions(fileset, {
    baseOptions: { modelAssetPath: '/mediapipe/hand_landmarker.task' },
    runningMode: 'VIDEO',
    numHands: 1,
  })
  return {
    detect(video) {
      const res = tracker.detectForVideo(video, performance.now())
      const hands = res && res.landmarks
      if (!hands || hands.length === 0) return 'None'
      return classifyGesture(hands[0])
    },
  }
}
