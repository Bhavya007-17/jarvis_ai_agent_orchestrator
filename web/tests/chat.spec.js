import { test, expect } from '@playwright/test'

test('shell loads and all six tabs are present', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('JARVIS')).toBeVisible()
  for (const name of ['Chat', 'Council', 'Connections', 'Memory', 'Tools', 'Settings']) {
    await expect(page.getByRole('button', { name })).toBeVisible()
  }
})

test('chat round-trips and shows the serving rung', async ({ page }) => {
  await page.goto('/')
  await page.getByPlaceholder('Ask Jarvis…').fill('say hello in one word')
  await page.getByPlaceholder('Ask Jarvis…').press('Enter')
  await expect(page.getByText(/served by/i)).toBeVisible({ timeout: 30000 })
})

test('settings exposes a model selector', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Settings' }).click()
  await expect(page.getByRole('combobox')).toBeVisible()
})

test('council tab renders the convene control', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Council' }).click()
  await expect(page.getByPlaceholder(/Planning task/i)).toBeVisible()
  await expect(page.getByRole('button', { name: /Convene/i })).toBeVisible()
})

test('connections tab shows the routing map', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Connections' }).click()
  await expect(page.getByText(/Routing map/i)).toBeVisible()
})

test('memory tab shows personal facts and a remember control', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Memory' }).click()
  await expect(page.getByText(/personal facts/i)).toBeVisible()
  await expect(page.getByRole('button', { name: /Remember/i })).toBeVisible()
})

test('tools tab lists MCP servers and an add control', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Tools' }).click()
  await expect(page.getByRole('heading', { name: /MCP servers/i })).toBeVisible()
  await expect(page.getByRole('button', { name: /Add server/i })).toBeVisible()
})
