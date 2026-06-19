# Jarvis — Build Progress

Read this at the start of every session to resume. Update as work proceeds.
Status values: `not-started` / `in-progress` / `passed`.

## Phase status

| Phase | Name | Status | Notes |
|------:|------|--------|-------|
| −1 | Bootstrap | `passed` | GATE met: `uv run jarvis --help` works. OpenJarvis in root, 5 refs in `_vendor/`, `.gitignore` extended, `uv sync` ok (core-only, no vllm), `.env` template scaffolded. Ollama `qwen2.5:7b` (4.7 GB) pulled and confirmed via `ollama list`. |
| 0 | Backbone + NIM wiring | `passed` | GATE met: `jarvis ask`→NIM (`pong`), `verify_models.py` PASS (7/7), local ollama answers. Extras installed (litellm 1.81.14, fastapi, google-genai, anthropic). NIM wired via LiteLLM **native `nvidia_nim/` provider** (engine discovery ignores `api_base`, so config-only OpenAI-compat route impossible). Active config generated at `~/.openjarvis/config.toml`. Launcher `scripts/jarvis.ps1` loads `.env` + maps `NVIDIA_API_KEY→NVIDIA_NIM_API_KEY`. Fixed 3 drifted model IDs in `.env`. |
| 1 | Router + multi-model fallback | `passed` | GATE met: code task→code model (qwen3.5), planning→reasoning (nemotron); `--simulate-nim-down`→Gemini(rate-limited, backed off 1s/2s)→local ollama, no crash; `doctor` shows health + per-task map. Built `scripts/jarvis_router.py` (classify + ladder + doctor, all via `LiteLLMEngine`). Mirrored MiniMax block in `cloud_router.py` → added `"nvidia"` provider (`_nim_models()`, get_provider branch, stream_cloud dispatch, NVIDIA_API_KEY in `_load_keys`) — structurally verified. NOTE: did NOT retrofit skillorchestra (heavyweight research prompt-router; retrofitting = rewrite, against prime directive) — used a thin router instead. |
| 2 | MCP drop-in + GitHub | `passed` | GATE met: `verify_mcp.py` discovers 15 MCP tools via OpenJarvis's own loader (14 codebase-memory + agent-reach `get_status`); `jarvis ask --agent operative` made a real codebase-memory tool call (`list_projects` → 31181 nodes, exact match to index); graph UI serves real 13.4 MB layout at `localhost:9749` (Jarvis repo indexed: 31181 nodes/143055 edges); Agent-Reach web fetch (Jina) returns real markdown. Wired by extending `setup_config.py` to emit `config.tools.mcp.servers` (2 stdio servers) — reuses `mcp/loader.py`+`ask.py`, no vendor/backbone edits. Installed: codebase-memory-mcp 0.8.1 **UI** binary (`install.ps1 --ui --skip-config`), gh 2.95.0 (winget), agent-reach 1.5.0 + mcp 1.28.0 (`uv pip` into `.venv`). Fixed Windows cp1252→UTF-8 MCP stdio decode via `PYTHONUTF8=1` in `jarvis.ps1`. **FOLLOW-UP:** GitHub arm needs interactive `gh auth login` (user); UI is a manually-started process. |
| 3 | Memory | `passed` | GATE met: `verify_memory.py` PASS (all 3 scopes); **live durable recall** — stored `identity/callsign=Bluefin-Seven`, a fresh `jarvis ask` (NIM) answered "Bluefin-Seven" (separate process = later turn), then forgot it. Ported Mark-XL `memory_manager.py` structured-facts logic → `scripts/jarvis_memory.py` (`FactsStore` at `~/.openjarvis/personal_facts.json`), **rendered into `~/.openjarvis/USER.md`** which OpenJarvis's `SystemPromptBuilder` already injects (`prompt/builder.py` → `cli/ask.py:397`) — no backbone/vendor edits. Scopes: `personal_facts` (facts→USER.md), `session` (reuses pure-Python `sessions/SessionStore`), `code_graph` (reuses Phase 2 cbm MCP). NOTE: did NOT use OpenJarvis's vector backend (`jarvis memory`) — sqlite/bm25 hard-require native `openjarvis_rust` (`RUST_AVAILABLE=False`); the facts port needs no Rust. |
| 4 | Council (planning only) | `passed` | GATE met: one `jarvis_council.py` run produced **3 distinct proposals** (Llama-70B/Qwen3.5/DeepSeek-v4 — the 3 distinct `NIM_COUNCIL_*` families, each with a distinct lens: Pragmatist/Architect/Skeptic), **1 critique** + **1 synthesized plan** on the reasoning model (Nemotron, `enable_thinking=true` via `extra_body`), and a **single executor** model (Llama-70B general) ran STEP 1 — no 429 storm (sequential, every voice served on its primary NIM rung). Built `scripts/jarvis_council.py` (propose→critique→synthesize→execute) **reusing** Phase-1 `complete_with_fallback` (added a backward-compatible `ladder=` param so each voice rides a specific-model-first ladder with the same backoff) + the `a2a` `A2ATask` state machine (state + per-voice history). Streams each voice (engine `stream()`, falls back to laddered sync on any stream error). **FOLLOW-UP:** `synthesis_directive()` left as a thin, documented policy seam (default = critic-weighted merge) for the user to tune. |
| 5 | Web UI | `in-progress` | **Slice 1 (Chat spine) done + verified.** Thin FastAPI sidecar `scripts/jarvis_web_api.py` (:8700): `/api/health`, `/api/models`, `WS /api/chat` streaming through the **Phase-1 router** (`complete_with_fallback`) so web chat inherits NIM→Gemini→local fallback + routing. `web/` Vite+React+Tailwind forked from ada_v2, **Electron stripped**; tab shell (Chat/Settings), model switch w/o restart. Launcher `scripts/jarvis_web.ps1`. Tests: `tests/web/test_sidecar.py` 4/4 PASS; live in-process WS chat → real NIM-A streamed `Hello` (rung→chunk→done); `vite build` compiles (1397 modules). **Remaining slices:** Council / Graph / Memory / Tools tabs + the live browser Playwright run. |
| 6 | Voice | `not-started` | |

## Environment (verified 2026-06-19)
- git 2.52.0 · uv 0.11.21 (Python 3.11 host) · node v24.13.0 · npm present · ollama 0.30.7 — all on PATH.
- Reference docs present in project folder: `jarvis-orchestrator-spec.md`,
  `jarvis-cursor-prompts.md`, `bootstrap.ps1`, `claude-code-build-prompt.md`.

## Session log
- **2026-06-19 (session 1):** Verified toolchain. Read all three reference docs. Wrote
  `CLAUDE.md` + `PROGRESS.md`. Resolved build-location ambiguity → user chose
  `projectfiles\Jarvis\`. Completed Phase −1: OpenJarvis via `git init`+fetch+checkout (no
  clobber of our docs), 5 vendor repos cloned, `.gitignore` extended, `uv sync` (63 pkgs, core
  only), `.env` template written, Ollama pull started. **Phase −1 GATE passed.** Awaiting user
  "go" + real keys in `.env` before Phase 0.

- **2026-06-19 (session 1, cont.):** Phase 0 done. Installed extras. Discovered engine
  discovery (`engine/_discovery.py:_make_engine`) constructs `LiteLLMEngine()` with **no
  api_base** → used LiteLLM's native `nvidia_nim/` provider instead of the OpenAI-compat
  route. Built `scripts/verify_models.py` (caught 3 drifted IDs → fixed in `.env`),
  `scripts/setup_config.py` (env→`~/.openjarvis/config.toml`), `scripts/jarvis.ps1` (loads
  `.env`, maps key). **Phase 0 GATE passed.** Awaiting "go" for Phase 1.

- **2026-06-19 (session 1, cont.):** Phase 1 done + gate-passed. `scripts/jarvis_router.py`
  (route + fallback ladder + doctor); `cloud_router.py` NIM provider mirror. Gemini free tier
  rate-limits on generate (model `gemini/gemini-2.0-flash`) — ladder degrades to local cleanly;
  consider a higher-quota Gemini model later. Next: Phase 2 (MCP drop-in: codebase-memory-mcp
  on `:9749` + Agent-Reach + GitHub auth) via `src/openjarvis/mcp/` + `jarvis add`.

- **2026-06-19 (session 2):** Phase 2 done + gate-passed. Read OpenJarvis `mcp/loader.py`+`ask.py`
  first → real consumption path is `config.tools.mcp.servers` (JSON list), NOT `jarvis add`
  (that writes to `~/.openjarvis/mcp/*.json`, which the loader never reads). Wired by extending
  `setup_config.py` (`build_mcp_servers()` auto-detects cbm binary + agent-reach venv python;
  emits servers as a TOML literal-string JSON array so Windows `\` round-trips through
  `json.loads`). Added `scripts/verify_mcp.py` (gate check via the real loader → 15 tools).
  Installs: cbm 0.8.1 **UI** binary via `_vendor/codebase-memory-mcp/install.ps1 --ui --skip-config`
  (→ `%LOCALAPPDATA%\Programs\codebase-memory-mcp\`), gh 2.95.0 (winget `GitHub.cli`),
  agent-reach 1.5.0 + mcp 1.28.0 (`uv pip install -e _vendor/Agent-Reach "mcp[cli]"`). Indexed
  Jarvis repo (31181 nodes/143055 edges; `.venv`+`_vendor` auto-excluded). Discovered:
  Agent-Reach's MCP server only exposes `get_status` by design (glue layer — real GitHub/web
  fetches go through `gh`/Jina, not MCP). Encoding fix: MCP stdio uses `Popen(text=True)` →
  cp1252 on Windows → `charmap` crash on agent-reach's emoji/CJK; fixed with `PYTHONUTF8=1`
  in `jarvis.ps1` (env-level, no backbone patch). **Open follow-ups:** (1) `gh auth login`
  (interactive — user) to unlock the GitHub fetch arm; (2) cbm UI is a manually-started
  process — currently running for the gate but not a service.

- **2026-06-19 (session 3):** Phase 3 done + gate-passed. Read OpenJarvis memory surface
  first → found it already has the right seams: `prompt/builder.py` injects SOUL/MEMORY/USER.md
  into every system prompt (used by `cli/ask.py`), and a pure-Python `sessions/SessionStore`.
  Its vector backend (`tools/storage/*`, `jarvis memory`) is Rust-only and unavailable here
  (`RUST_AVAILABLE=False`). Ported Mark-XL's structured-facts logic into
  `scripts/jarvis_memory.py` (`FactsStore` → `personal_facts.json`, dedup + date-stamped +
  self-trimming) and rendered it into a sentinel-delimited block of `USER.md` so the existing
  prompt builder carries it — zero backbone/vendor edits. Added `scripts/verify_memory.py`
  (3-scope gate; closes sqlite conns so Windows can clean temp dirs). Live recall verified via
  NIM. **Open follow-ups:** (1) optional — build `openjarvis_rust` (maturin, rustc >= 1.88) to
  unlock semantic `jarvis memory` search + RAG `inject_context`; (2) DONE — LLM-driven
  auto-extraction scaffolded in `scripts/jarvis_automem.py` (extract via NIM + fallback ladder
  → `decide_fact` policy seam → FactsStore). Verified live `--dry-run`: pulled name/university/
  language prefs, dropped the transient weather question. The `decide_fact` policy is left as a
  deliberately thin, documented TODO for the user to tune (confidence bar, overwrite-vs-keep).

- **2026-06-19 (session 4):** Phase 4 done + gate-passed. Read `a2a/protocol.py`, the
  Phase-1 router, the engine, and superpowers `writing-plans`/`brainstorming` first → the
  council is a *pipeline of LLM calls*, not new infra, so it reuses the existing reliable
  primitive rather than re-implementing backoff. Extended `complete_with_fallback` with an
  optional `ladder=` param (backward compatible; `jarvis_automem.py` call site unaffected) so
  each council voice rides a specific-model-first ladder with the same exponential backoff +
  NIM→Gemini→local fallback (this is what prevents the 429 storm the spec warns about). Built
  `scripts/jarvis_council.py`: 3 proposers on distinct `NIM_COUNCIL_*` families, each given a
  distinct lens (Pragmatist/Architect/Skeptic) for real diversity; critic + synthesizer on the
  Nemotron reasoning model with `extra_body={"chat_template_kwargs":{"enable_thinking":true}}`
  (passthrough confirmed clean — no leaked `<think>` tags); single executor on the general
  model runs STEP 1. Deliberation is carried in an `a2a.A2ATask` (state machine + per-voice
  history). Streams each voice via the engine's async `stream()`, falling back to the laddered
  sync call on any stream error (live UX + guaranteed completion). **Open follow-up:** the
  `synthesis_directive()` consensus policy is a thin, documented seam (default = critic-weighted
  merge; alternatives winner-take-all / merge-strengths noted in the docstring) for the user to
  tune — mirrors Phase 3's `decide_fact` pattern.

- **2026-06-19 (session 5):** Phase 5 **slice 1** (Chat spine) built via brainstorm→spec→plan→subagent/inline TDD. Spec `docs/superpowers/specs/2026-06-19-phase5-web-ui-design.md`, plan `docs/superpowers/plans/2026-06-19-phase5-slice1-chat.md`. Branch `phase5-web-ui-slice1` (4 commits `44f4f1e..e365144`). Decisions: thin sidecar (no backbone/vendor edits), vertical-slice-first, reuse ada_v2 dark look, chat through Phase-1 router. Sidecar streams the top rung via `engine.stream`, falls back to laddered `complete_with_fallback` on any stream error (same pattern as Phase-4 council). Model switch = per-request `model` field on the WS message (no server state). Verified live: health/models OK, real NIM-A WS chat streamed. **Open follow-ups:** run the launcher + Playwright in a real browser (needs chromium download) for the full Phase-5 gate; then Council/Graph/Memory/Tools slices.

## Open decisions
- _(resolved)_ Build location → `C:\Users\bhavy\Desktop\projectfiles\Jarvis\`.
- _(resolved)_ Phase 3 personal_facts storage → ported Mark-XL JSON facts (no Rust), rendered
  into OpenJarvis `USER.md`; vector/RAG backend deferred pending `openjarvis_rust` build.

## How to run (current)
- `pwsh .\scripts\jarvis.ps1 ask "..."` — NIM default (loads `.env`, sets `NVIDIA_NIM_API_KEY`).
- `pwsh .\scripts\jarvis.ps1 ask -e ollama -m qwen2.5:7b "..."` — offline fallback.
- `uv run python scripts/verify_models.py` — validate NIM key + model IDs.
- `uv run python scripts/setup_config.py` — regenerate active config (model IDs + MCP servers).
- `uv run python scripts/verify_mcp.py` — Phase 2 gate: discover MCP tools via the real loader.
- `uv run python scripts/jarvis_memory.py remember -c identity name "..."` — store a personal fact.
- `uv run python scripts/jarvis_memory.py show | forget | render | session | code` — manage memory scopes.
- `uv run python scripts/verify_memory.py` — Phase 3 gate: verify personal_facts/session/code_graph.
- `uv run python scripts/jarvis_automem.py --dry-run "..."` — LLM auto-extract facts (policy in `decide_fact`).
- `uv run python scripts/jarvis_council.py "<planning task>"` — Phase 4 council: propose×3 → critique → synthesize → execute (consensus policy in `synthesis_directive`).
- `uv run python scripts/jarvis_council.py --no-execute "..."` — planning only (stop after the synthesized plan); `--no-stream` for laddered (non-streamed) calls.
- `codebase-memory-mcp --ui=true --port=9749` — start the code-graph UI (http://localhost:9749).
- `codebase-memory-mcp cli index_repository "{\"repo_path\":\"<abs/path>\"}"` — index a repo into the graph.
- `gh auth login` — (user, interactive) unlock Agent-Reach's GitHub fetch path.

- `pwsh .\scripts\jarvis_web.ps1` — Phase 5 Web UI: starts sidecar (:8700) + Vite dev (:5173), loads `.env`.
- `uv run pytest tests/web/test_sidecar.py -v` — Phase 5 slice-1 sidecar tests (health/models/chat-WS).
- `cd web; npx playwright install chromium; npx playwright test` — slice-1 browser smoke (launcher must be running).

## Key architecture facts (learned)
- **Two LLM paths:** (1) engine `LiteLLMEngine→litellm.completion` (reads `os.environ`) used by
  `jarvis ask`; (2) `server/cloud_router.py` direct-httpx (reads `~/.openjarvis/cloud-keys.env`).
- NIM extras: `uv sync --extra inference-litellm --extra server --extra inference-google --extra inference-cloud`.
- Reasoning kwarg passthrough confirmed: `litellm.py:63` `call_kwargs.update(kwargs)` →
  `extra_body={"chat_template_kwargs":{"enable_thinking":bool}}` will flow (Phase 4).
- **MCP wiring path (Phase 2):** the orchestrator reads MCP servers ONLY from
  `config.tools.mcp.servers` (a JSON string; `mcp/loader.py` does `json.loads`, then
  StdioTransport for `command` / StreamableHTTPTransport for `url`). `jarvis add` writes
  `~/.openjarvis/mcp/*.json` which is NOT on this path — ignore it; configure servers via
  `setup_config.py`. `ask.py` stashes `agent._mcp_clients` to keep transports alive.
- **cbm UI / :9749 (Phase 5 will embed this):** `codebase-memory-mcp --ui=true --port=9749`
  serves a Vite SPA; graph data at `GET /api/layout?project=<path-derived-name>` (also
  `/api/project-health`, `/api/index`, `/api/processes`). Graph is namespaced by repo path.
- **Windows MCP-stdio encoding:** `StdioTransport` uses `Popen(text=True)` → cp1252 →
  crashes on non-ASCII tool output. Always run jarvis with `PYTHONUTF8=1` (set in `jarvis.ps1`).
- **Memory wiring (Phase 3):** OpenJarvis injects persistent files into the *frozen prefix* of
  every system prompt via `prompt/builder.py` (`SystemPromptBuilder`): `SOUL.md`→Agent Persona,
  `MEMORY.md`→Agent Memory, `USER.md`→User Profile. Paths come from `config.memory_files`
  (`MemoryFilesConfig`, defaults under `~/.openjarvis/`). `cli/ask.py:397` constructs the
  builder, so anything written to `USER.md` is recalled on every later `jarvis ask`. Phase 3's
  `personal_facts` rides this seam (renders a sentinel-delimited block into USER.md).
- **Vector memory is Rust-gated:** `tools/storage/*` backends (sqlite/bm25, the `jarvis memory`
  CLI, and `inject_context` RAG in `system/orchestrator.py`/`sdk.py`/`server/routes.py`) all go
  through `_rust_bridge.get_rust_module()` and raise `MemoryBackendUnavailable` when the native
  ext is absent. `RUST_AVAILABLE=False` here — build with
  `uv run maturin develop -m rust/crates/openjarvis-python/Cargo.toml` (rustc >= 1.88) to enable.
