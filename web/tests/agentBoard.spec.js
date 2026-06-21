import { test, expect } from '@playwright/test'

const MODELS = {
  task_map: { reasoning: 'nvidia/r', code: 'nvidia/c', general: 'nvidia/g' },
  models: ['auto', 'nvidia/r', 'nvidia/c', 'nvidia/g'],
}

async function stubModels(page) {
  await page.route('**/api/models', (route) =>
    route.fulfill({ json: MODELS }))
}

test('dragging (click-add) an agent places a node and a pipe', async ({ page }) => {
  await stubModels(page)
  await page.route('**/api/board', (route) =>
    route.fulfill({ json: { nodes: [], edges: [], models: {} } }))

  await page.goto('/')
  await page.getByRole('button', { name: 'Agents' }).click()

  // palette renders the personality library
  await expect(page.getByRole('button', { name: /Add Architect/ })).toBeVisible()

  // add Architect to the board
  await page.getByRole('button', { name: /Add Architect/ }).click()

  // a board node + a pipe edge appear
  await expect(page.locator('.react-flow__node-agent')).toHaveCount(1)
  await expect(page.locator('.react-flow__node-agent')).toContainText('Architect')
  await expect(page.locator('.react-flow__edge')).toHaveCount(1)
})

test('saved board restores on load', async ({ page }) => {
  await stubModels(page)
  await page.route('**/api/board', (route) =>
    route.fulfill({
      json: {
        nodes: [{ id: 'a_coder_1', persona: 'coder', model: 'nvidia/c',
                  x: 120, y: 140, benched: false }],
        edges: [{ id: 'e_a_coder_1', source: 'orchestrator', target: 'a_coder_1' }],
        models: { coder: 'nvidia/c' },
      },
    }))

  await page.goto('/')
  await page.getByRole('button', { name: 'Agents' }).click()

  await expect(page.locator('.react-flow__node-agent')).toContainText('Coder')
  await expect(page.locator('.react-flow__edge')).toHaveCount(1)
})
