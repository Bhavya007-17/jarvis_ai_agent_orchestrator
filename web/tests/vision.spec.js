import { test, expect } from '@playwright/test'

// Build a 21-point hand where chosen fingertips are "extended" (tip.y < pip.y).
// Fingertips 8/12/16/20 with pips 6/10/14/18; thumb tip 4 / ip 3; wrist refs 5,17.
function hand({ index = false, middle = false, ring = false, pinky = false, pinch = false } = {}) {
  const lm = Array.from({ length: 21 }, () => ({ x: 0.5, y: 0.5, z: 0 }))
  const setFinger = (tip, pip, extended) => {
    lm[pip] = { x: 0.5, y: 0.5, z: 0 }
    lm[tip] = { x: 0.5, y: extended ? 0.2 : 0.8, z: 0 } // extended => tip above pip
  }
  setFinger(8, 6, index); setFinger(12, 10, middle)
  setFinger(16, 14, ring); setFinger(20, 18, pinky)
  lm[5] = { x: 0.6, y: 0.5, z: 0 }; lm[17] = { x: 0.4, y: 0.5, z: 0 } // 5.x > 17.x
  lm[3] = { x: 0.5, y: 0.5, z: 0 }; lm[4] = { x: 0.45, y: 0.5, z: 0 } // thumb folded
  if (pinch) { lm[4] = { x: 0.5, y: 0.5, z: 0 }; lm[8] = { x: 0.51, y: 0.51, z: 0 } }
  return lm
}

test('classifyGesture recognizes the mapped gestures', async ({ page }) => {
  await page.goto('http://localhost:5173/')
  const classify = (landmarks) =>
    page.evaluate(async (lms) => {
      const m = await import('/src/lib/handGestures.js')
      return m.classifyGesture(lms)
    }, landmarks)

  expect(await classify(hand({ index: true, middle: true, ring: true, pinky: true }))).toBe('Open Palm')
  expect(await classify(hand({}))).toBe('Closed Fist')
  expect(await classify(hand({ index: true, middle: true }))).toBe('Peace Sign')
  expect(await classify(hand({ index: true, middle: true, ring: true, pinky: true, pinch: true }))).toBe('Pinching')
})

// AuthLock unlock via injected fake recognizer. The app reads window.__VISION_FAKE__
// so we can drive recognition deterministically without a camera or WASM.
test('AuthLock unlocks on a verified match', async ({ page }) => {
  await page.addInitScript(() => {
    window.__VISION_FAKE__ = {
      faceFactory: async () => ({ extract: () => [0.1, 0.2, 0.3] }),
    }
  })
  await page.route('**/api/vision/status', (r) =>
    r.fulfill({ json: { enrolled: true, lock_enabled: true } }))
  await page.route('**/api/vision/verify', (r) =>
    r.fulfill({ json: { match: true, similarity: 0.99 } }))

  await page.goto('http://localhost:5173/')
  await expect(page.getByText('SYSTEM LOCKED')).toBeVisible()
  await expect(page.getByText('SYSTEM UNLOCKED')).toBeVisible({ timeout: 5000 })
})

// Gesture fires a mapped window action.
test('Open Palm gesture opens the Chat window', async ({ page }) => {
  await page.addInitScript(() => {
    window.__VISION_FAKE__ = {
      faceFactory: async () => ({ extract: () => [0.1, 0.2, 0.3] }),
      handFactory: async () => {
        const seq = ['None', 'Open Palm', 'Open Palm']
        let i = 0
        return { detect: () => seq[Math.min(i++, seq.length - 1)] }
      },
    }
  })
  await page.route('**/api/vision/status', (r) =>
    r.fulfill({ json: { enrolled: false, lock_enabled: false } }))

  await page.goto('http://localhost:5173/')
  await page.getByRole('button', { name: 'Vision' }).click()
  await page.getByRole('button', { name: /gesture/i }).click()
  await expect(page.getByText('Chat', { exact: false })).toBeVisible({ timeout: 5000 })
})

test('Visualizer canvas renders inside the Vision module', async ({ page }) => {
  await page.route('**/api/vision/status', (r) =>
    r.fulfill({ json: { enrolled: false, lock_enabled: false } }))
  await page.goto('http://localhost:5173/')
  await page.getByRole('button', { name: 'Vision' }).click()
  await expect(page.locator('canvas')).toBeVisible()
})
