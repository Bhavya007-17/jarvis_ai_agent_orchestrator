import { test, expect } from '@playwright/test'

test('chat round-trips and shows the serving rung', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('JARVIS')).toBeVisible()
  await page.getByPlaceholder('Ask Jarvis…').fill('say hello in one word')
  await page.getByPlaceholder('Ask Jarvis…').press('Enter')
  // A Jarvis bubble appears and eventually shows the serving rung tag.
  await expect(page.getByText(/served by/i)).toBeVisible({ timeout: 30000 })
})

test('settings exposes a model selector', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /settings/i }).click()
  await expect(page.getByRole('combobox')).toBeVisible()
})
