// tests/web/voice.spec.js
const { test, expect } = require('@playwright/test')

test('voice tab renders and starts', async ({ page }) => {
  await page.goto('http://localhost:5173')
  await page.getByRole('button', { name: 'Voice' }).click()
  await expect(page.getByText('Start always-on')).toBeVisible()
  await page.getByRole('button', { name: 'Start always-on' }).click()
  // With fake media (see run note) the mic grant succeeds and status flips.
  await expect(page.getByText(/Status:/)).toBeVisible()
})
