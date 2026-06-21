import { test, expect } from '@playwright/test'

const MODELS = { task_map: { reasoning: 'nvidia/r', code: 'nvidia/c', general: 'nvidia/g' }, models: ['auto', 'nvidia/r'] }

async function stubBackend(page, layout = { windows: {} }) {
  await page.route('**/api/models', (r) => r.fulfill({ json: MODELS }))
  await page.route('**/api/ui-layout', (r) => {
    if (r.request().method() === 'PUT') return r.fulfill({ json: { ok: true, layout } })
    return r.fulfill({ json: layout })
  })
}

test('shell loads with a bottom bar and no left rail', async ({ page }) => {
  await stubBackend(page)
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Chat' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Settings' })).toBeVisible()
  // no window is open initially
  await expect(page.locator('[data-window-id]')).toHaveCount(0)
})

test('clicking a bar icon opens that module window', async ({ page }) => {
  await stubBackend(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'Chat' }).click()
  await expect(page.locator('[data-window-id="chat"]')).toBeVisible()
})

test('multiple windows coexist', async ({ page }) => {
  await stubBackend(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'Chat' }).click()
  await page.getByRole('button', { name: 'Memory' }).click()
  await expect(page.locator('[data-window-id="chat"]')).toBeVisible()
  await expect(page.locator('[data-window-id="memory"]')).toBeVisible()
})

test('dragging a window header moves it', async ({ page }) => {
  await stubBackend(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'Chat' }).click()
  const win = page.locator('[data-window-id="chat"]')
  const before = await win.boundingBox()
  const header = win.locator('[data-drag-handle]')
  const hb = await header.boundingBox()
  await page.mouse.move(hb.x + hb.width / 2, hb.y + hb.height / 2)
  await page.mouse.down()
  await page.mouse.move(hb.x + hb.width / 2 - 160, hb.y + hb.height / 2 + 40, { steps: 8 })
  await page.mouse.up()
  const after = await win.boundingBox()
  expect(Math.abs(after.x - before.x)).toBeGreaterThan(40)
})

test('saved-open layout restores on load', async ({ page }) => {
  await stubBackend(page, { windows: { council: { x: 500, y: 300, open: true, z: 31 } } })
  await page.goto('/')
  await expect(page.locator('[data-window-id="council"]')).toBeVisible()
})

test('wrapped Chat tab still renders its content inside the window', async ({ page }) => {
  await stubBackend(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'Chat' }).click()
  // ChatTab renders a message input — assert the window contains an editable field
  await expect(page.locator('[data-window-id="chat"] textarea, [data-window-id="chat"] input')).toHaveCount(1)
})
