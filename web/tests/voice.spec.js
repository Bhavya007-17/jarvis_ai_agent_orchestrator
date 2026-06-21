import { test, expect } from '@playwright/test'

test('voice tab renders and starts always-on', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Voice' }).click()
  await expect(page.getByRole('button', { name: 'Start always-on' })).toBeVisible()
  // Fake media (configured in playwright.config.js) auto-grants the mic so the
  // worklet/socket path starts without a real device.
  await page.getByRole('button', { name: 'Start always-on' }).click()
  await expect(page.getByText(/status/i).first()).toBeVisible()
})
