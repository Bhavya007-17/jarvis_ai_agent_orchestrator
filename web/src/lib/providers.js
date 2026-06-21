import { getJSON, postJSON } from './api'

// Phase 7 — provider keys. The backend returns presence booleans only; a key
// value is never sent back, so nothing here ever holds a saved key.

// -> { providers: { openai: bool, ... }, known: [ids] }
export async function fetchProviders() {
  const d = await getJSON('/api/providers')
  return d.error ? { providers: {}, known: [] } : d
}

// Save a key. Returns { ok, providers } (no key value). The caller clears its
// input on success so the secret never lingers in component state.
export async function saveProviderKey(provider, key) {
  return postJSON('/api/providers', { provider, key })
}

// Friendly display names for the known provider ids.
export const PROVIDER_LABELS = {
  openai: 'OpenAI',
  anthropic: 'Anthropic (Claude)',
  groq: 'Groq',
  openrouter: 'OpenRouter',
  mistral: 'Mistral',
}
