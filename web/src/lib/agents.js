// The Agent Board personality catalog. Each agent is a {persona, lens, model}
// the council can convene (see scripts/jarvis_council.py:run_council). Models are
// NEVER hardcoded here — `defaultModelKey` resolves to a concrete id from
// /api/models at runtime, so .env stays the single source of truth.

/**
 * @typedef {Object} Agent
 * @property {string} id            stable slug (must match server BOARD_PERSONAS)
 * @property {string} persona       display name + council label
 * @property {string} lens          system-prompt guidance that shapes proposals
 * @property {string} defaultModelKey  one of: reasoning | code | general
 * @property {string} accent        HUD accent color
 * @property {string} blurb         one-line palette description
 */

/** @type {Agent[]} */
export const AGENT_CATALOG = [
  {
    id: 'architect', persona: 'Architect', defaultModelKey: 'reasoning', accent: '#22d3ee',
    lens: 'You favor long-term structure: clean boundaries, scalability, and maintainability. Think about how this evolves over the next year.',
    blurb: 'Long-term structure & scalability',
  },
  {
    id: 'skeptic', persona: 'Skeptic', defaultModelKey: 'reasoning', accent: '#f472b6',
    lens: 'You hunt failure modes. Surface edge cases, race conditions, security and cost risks, and the ways a naive approach breaks in production.',
    blurb: 'Failure modes & risk hunting',
  },
  {
    id: 'pragmatist', persona: 'Pragmatist', defaultModelKey: 'general', accent: '#34d399',
    lens: 'You favor the simplest thing that works. Optimize for shipping fast with the least risk and moving parts. Call out what to NOT build.',
    blurb: 'Simplest thing that ships',
  },
  {
    id: 'coder', persona: 'Coder', defaultModelKey: 'code', accent: '#a78bfa',
    lens: 'You think in concrete implementation. Propose specific files, functions, and code-level steps. Prefer working code over abstract description.',
    blurb: 'Concrete implementation steps',
  },
  {
    id: 'researcher', persona: 'Researcher', defaultModelKey: 'general', accent: '#60a5fa',
    lens: 'You gather evidence before deciding. Identify what is unknown, what to verify, and which sources or experiments would settle each open question.',
    blurb: 'Evidence-first investigation',
  },
  {
    id: 'creative', persona: 'Creative', defaultModelKey: 'general', accent: '#fbbf24',
    lens: 'You look for the non-obvious angle. Propose at least one unconventional approach the others would miss, and explain why it might be better.',
    blurb: 'Unconventional angles',
  },
  {
    id: 'fact-checker', persona: 'Fact-checker', defaultModelKey: 'reasoning', accent: '#2dd4bf',
    lens: 'You challenge every claim. Flag assumptions stated as facts, demand they be grounded, and separate what is known from what is merely assumed.',
    blurb: 'Challenges assumptions',
  },
  {
    id: 'planner', persona: 'Planner', defaultModelKey: 'reasoning', accent: '#818cf8',
    lens: 'You decompose work into an ordered, dependency-aware sequence. Produce small, verifiable steps with clear hand-offs between them.',
    blurb: 'Ordered, step-by-step plans',
  },
]

const BY_ID = Object.fromEntries(AGENT_CATALOG.map((a) => [a.id, a]))

/** @param {string} id @returns {Agent | undefined} */
export function agentById(id) {
  return BY_ID[id]
}

/**
 * Resolve an agent's concrete model id from the /api/models task map.
 * Falls back across keys, then to the first non-'auto' model, so an agent
 * always has a usable model even if a .env task slot is empty.
 * @param {Agent} agent
 * @param {{ task_map?: Record<string,string>, models?: string[] }} models
 * @returns {string}
 */
export function resolveModel(agent, models) {
  const map = (models && models.task_map) || {}
  const order = [agent.defaultModelKey, 'general', 'reasoning', 'code']
  for (const key of order) {
    if (map[key]) return map[key]
  }
  const list = ((models && models.models) || []).filter((m) => m && m !== 'auto')
  return list[0] || ''
}
