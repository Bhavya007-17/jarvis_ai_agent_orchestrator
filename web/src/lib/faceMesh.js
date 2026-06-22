// web/src/lib/faceMesh.js
// Lazy MediaPipe FaceLandmarker loader. extract(video) -> flattened [x,y,z] vector.
import { FilesetResolver, FaceLandmarker } from '@mediapipe/tasks-vision'

export async function createFaceMesh() {
  const fileset = await FilesetResolver.forVisionTasks('/mediapipe/wasm')
  const landmarker = await FaceLandmarker.createFromOptions(fileset, {
    baseOptions: { modelAssetPath: '/mediapipe/face_landmarker.task' },
    runningMode: 'VIDEO',
    numFaces: 1,
  })
  return {
    extract(video) {
      const res = landmarker.detectForVideo(video, performance.now())
      const faces = res && res.faceLandmarks
      if (!faces || faces.length === 0) return null
      const pts = faces[0]
      const out = new Float32Array(pts.length * 3)
      for (let i = 0; i < pts.length; i++) {
        out[i * 3] = pts[i].x
        out[i * 3 + 1] = pts[i].y
        out[i * 3 + 2] = pts[i].z
      }
      return out
    },
  }
}
