import { test, expect } from '@playwright/test'

// Phase 9 — agent graph. Deterministic + launcher-free: stub /api/models +
// /api/board (a seeded chain proposers -> fact-checker -> orchestrator) and mock
// the /api/graph WebSocket so we drive the exact frame protocol the board maps.

const MODELS = {
  task_map: { reasoning: 'nvidia/r', code: 'nvidia/c', general: 'nvidia/g' },
  models: ['auto', 'nvidia/r', 'nvidia/c', 'nvidia/g'],
}

const SEED = {
  nodes: [
    { id: 'a_pragmatist_1', persona: 'pragmatist', model: 'nvidia/g', x: 60, y: 60 },
    { id: 'a_skeptic_1', persona: 'skeptic', model: 'nvidia/r', x: 60, y: 220 },
    { id: 'a_fact-checker_1', persona: 'fact-checker', model: 'nvidia/r', x: 300, y: 140 },
  ],
  edges: [
    { id: 'e1', source: 'a_pragmatist_1', target: 'a_fact-checker_1' },
    { id: 'e2', source: 'a_skeptic_1', target: 'a_fact-checker_1' },
    { id: 'e3', source: 'a_fact-checker_1', target: 'orchestrator' },
  ],
  models: {},
}

async function stub(page) {
  await page.route('**/api/models', (route) => route.fulfill({ json: MODELS }))
  await page.route('**/api/board', (route) => {
    if (route.request().method() === 'PUT') return route.fulfill({ json: { ok: true, board: SEED } })
    return route.fulfill({ json: SEED })
  })
}

// Mock the graph WebSocket: emit the frame protocol in topological order.
async function mockGraphWs(page) {
  await page.routeWebSocket('ws://localhost:8700/api/graph', (ws) => {
    ws.onMessage(() => {
      const send = (f) => ws.send(JSON.stringify(f))
      for (const id of ['a_pragmatist_1', 'a_skeptic_1']) {
        send({ type: 'node_start', node: id })
        send({ type: 'node_chunk', node: id, content: `from ${id}` })
        send({ type: 'node_end', node: id, content: `from ${id}`, model: 'nvidia/g' })
        send({ type: 'edge_flow', source: id, target: 'a_fact-checker_1' })
      }
      send({ type: 'node_start', node: 'a_fact-checker_1' })
      send({ type: 'node_chunk', node: 'a_fact-checker_1', content: 'checked' })
      send({ type: 'node_end', node: 'a_fact-checker_1', content: 'checked', model: 'nvidia/r' })
      send({ type: 'edge_flow', source: 'a_fact-checker_1', target: 'orchestrator' })
      send({ type: 'node_start', node: 'orchestrator' })
      send({ type: 'node_chunk', node: 'orchestrator', content: 'FINAL PLAN: do the thing' })
      send({ type: 'node_end', node: 'orchestrator', content: 'FINAL PLAN: do the thing', model: 'nvidia/r' })
      send({ type: 'graph_done', output: 'FINAL PLAN: do the thing' })
    })
  })
}

test('seeded chain graph renders nodes and drawn edges', async ({ page }) => {
  await stub(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'Agents' }).click()

  await expect(page.locator('.react-flow__node-agent')).toHaveCount(3)
  await expect(page.locator('.react-flow__node-agent').filter({ hasText: 'Fact-checker' })).toHaveCount(1)
  await expect(page.locator('.react-flow__edge')).toHaveCount(3)
})

test('running the graph streams nodes in order and renders the synthesized plan', async ({ page }) => {
  await stub(page)
  await mockGraphWs(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'Agents' }).click()

  await expect(page.locator('.react-flow__node-agent')).toHaveCount(3)

  await page.getByPlaceholder(/Give the graph a task/i).fill('design a small cache')
  await page.getByRole('button', { name: /^Run/ }).click()

  // The orchestrator's synthesized plan readout appears with the streamed output.
  await expect(page.getByText('synthesized plan')).toBeVisible({ timeout: 15000 })
  await expect(page.getByText('FINAL PLAN: do the thing')).toBeVisible()
})
