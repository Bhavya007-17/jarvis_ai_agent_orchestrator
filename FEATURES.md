# Jarvis — Next Features Roadmap

> Build entry-point for future sessions. Each phase below is a self-contained slice:
> open a fresh chat, point it at this file + the named source files, and build that
> one phase. **Order is a recommendation, not a law** — adjust to taste.
>
> Source-of-truth context: `CLAUDE.md`, `PROGRESS.md`,
> `docs/superpowers/specs/2026-06-21-agent-board-design.md` (the already-built Agent Board).

## 0. PRIME DIRECTIVE for every phase — PULL, don't rebuild

The capabilities below **already exist** in `_vendor/` repos and the ECC agent library.
**Port / wire / configure them — do NOT reimplement from scratch.** Before writing any
new code in a phase:

1. **Read the named source files first** and state what will be reused verbatim.
2. Clone any missing reference repo into `_vendor/<name>` (read-only; add to `.gitignore`).
3. Prefer copying a proven function and adapting its I/O over authoring a new one.
4. Wire through the existing sidecar (`scripts/jarvis_web_api.py`) + OpenJarvis engine —
   **no backbone/`_vendor` edits**, no new LLM path (every call rides the Phase-1
   router `complete_with_fallback` / `LiteLLMEngine.stream`).

If you catch yourself writing something a vendor repo already does → STOP and wire theirs.

---

## 1. What already exists (do not redo)

| Area | Status | Where |
|---|---|---|
| NIM + Gemini + Ollama routing, fallback ladder | done | `scripts/jarvis_router.py` |
| Multi-model council (propose->critique->synthesize) | done | `scripts/jarvis_council.py` |
| **Agent Board** (drag personas -> roster council, live pulsing pipes) | done | `web/src/components/AgentsTab.jsx` + `board/*`, `lib/agents.js` |
| Web sidecar (chat/council/voice/memory/MCP/board WS+REST) | done | `scripts/jarvis_web_api.py` |
| Memory (personal facts -> USER.md), MCP drop-in, voice (STT/TTS/wake) | done | Phases 3/2/6 |
| HUD/arc-reactor styling tokens | done | `web/src/index.css`, `tailwind.config.js` |

The Agent Board (Phase "B") ships a flat roster (all agents -> orchestrator). **Phase B+**
below upgrades it to an arbitrary agent-to-agent graph and a much bigger persona library.

---

## 2. Recommended phase order

| Phase | Slice | Why this order |
|---|---|---|
| **7** | **E — Provider keys from anywhere** | Foundational: unlocks OpenAI/Claude/etc. models that the bigger persona library, the graph, and Clicky's vision all want. Small. |
| **8** | **C — ada-style shell & UI** | The frame everything else lives in. Re-organize like ada now so later slices slot into the new shell instead of being retrofitted. |
| **9** | **B+ — Agent graph + ECC personas** | The brain: ECC agents as personas + user-drawn agent-to-agent "talk & reason" edges. Builds on the existing board, into the new shell. |
| **10** | **A — Vision & camera** | Face-auth, hand-gesture, visualizer. Self-contained; slots into the shell as modules. |
| **11** | **D — Action tools + F — Clicky** | Port Mark-XL/ada actions + Clicky screen-pointing as orchestrator tools. Clicky's vision depends on Phase 7 keys. |

Each phase = its own brainstorm->spec->build->gate cycle (mirror the existing specs).

---

## Phase 7 · E — Provider keys from anywhere

**Goal:** Paste an OpenAI / Anthropic(Claude) / Groq / OpenRouter / etc. key in the UI and
have its models immediately selectable across chat, council, board, and Clicky — `.env`
stays the single source of truth, keys are never echoed back.

**Pull from / wire, don't rewrite:**
- LiteLLM already routes any provider — reuse `scripts/jarvis_router.py` ladder + `_nim`/prefix
  logic; just add provider prefixes (`openai/`, `anthropic/`, `groq/`, `openrouter/`).
- Mirror the existing **MCP add-server** pattern in `jarvis_web_api.py`
  (`_load_mcp_servers`/`_write_mcp_servers`/`_validate_*`) for safe server-side `.env` writes.
- ada already has a settings persistence pattern: `_vendor/ada_v2/backend/server.py`
  `load_settings()` / `save_settings()` (port the read/merge/write shape).

**Backend (`jarvis_web_api.py`):**
- `GET /api/providers` -> list known providers + **presence only** (`{openai: true, anthropic: false}`), never the key value.
- `POST /api/providers` -> `{provider, key}` -> validate format -> write to `.env` (atomic, like `_write_board`) **and** set `os.environ[VAR]` live so `LiteLLMEngine` picks it up with no restart -> return presence booleans only.
- `GET /api/models` extended to include enabled-provider model ids (ids still come from `.env`, never hardcoded — add `OPENAI_MODELS`, `ANTHROPIC_MODELS`, ... comma-lists).

**`.env` — add commented placeholders (user fills in):**
```dotenv
# OPENAI_API_KEY=
# OPENAI_MODELS=openai/gpt-4.1-mini,openai/gpt-4.1
# ANTHROPIC_API_KEY=
# ANTHROPIC_MODELS=anthropic/claude-sonnet-4-6,anthropic/claude-opus-4-8
# GROQ_API_KEY=
# OPENROUTER_API_KEY=
# MISTRAL_API_KEY=
```

**Frontend:** `SettingsTab.jsx` -> add a **Providers** panel: per-provider masked input +
Save + a green/grey "configured" dot (driven by `GET /api/providers`). Never render a key value.

**Security:** key never returned by any GET; input masked; no logging; validate shape; reuse the
MCP validator hardening pattern. Per CLAUDE.md the user owns `.env` — this just gives a safe writer.

**Gate:** paste a Claude key in Settings -> a `claude-*` model appears in the model dropdowns ->
a chat/council run is served by it (rung label shows the new model) -> key never visible in UI or logs.

---

## Phase 8 · C — ada-style shell & UI (organized like ada)

**Goal:** Re-skin/re-organize the app to ada's layout — a **bottom feature bar** that opens
floating, draggable **module windows** over a central HUD, instead of the current left rail.
Keep all existing tabs working as windows.

**Pull from / wire, don't rewrite (this is mostly a port of ada's shell):**
- ada's window/module system — port these components and their open/close/focus logic:
  - `_vendor/ada_v2/src/components/TopAudioBar.jsx` -> re-base as the **bottom** feature bar.
  - `_vendor/ada_v2/src/components/{BrowserWindow,CadWindow,KasaWindow,PrinterWindow,SettingsWindow}.jsx`
    -> the **windowed-module** pattern (draggable panel chrome, header, close).
  - `_vendor/ada_v2/src/components/Visualizer.jsx` -> central idle visualizer (also used in Phase A).
  - `_vendor/ada_v2/src/components/{ChatModule,ToolsModule,ConfirmationPopup,MemoryPrompt}.jsx`
    -> module + confirmation-dialog patterns.
  - `_vendor/ada_v2/src/App.jsx` + `index.css` + `tailwind.config.js` -> ada's layout/organization & theme; merge with Jarvis's existing HUD tokens (`web/src/index.css`).

**Build:** a `web/src/shell/` with `BottomBar.jsx`, `ModuleWindow.jsx` (draggable, reuse
React Flow's drag math or ada's), `useWindows.js` (open/close/z-order state, no localStorage —
persist layout via a `/api/ui-layout` endpoint mirroring `/api/board`). Wrap each existing tab
(`ChatTab`, `AgentsTab`, `CouncilTab`, `GraphTab`, `MemoryTab`, `ToolsTab`, `VoiceTab`, `SettingsTab`)
as a module window launched from the bottom bar.

**Gate:** app loads with a bottom feature bar; clicking an icon opens that module as a
draggable window; multiple windows coexist; layout persists across reload; existing tab
functionality unchanged inside its window.

---

## Phase 9 · B+ — Agent graph (ECC personas + agent-to-agent talk & reason)

**Goal:** Upgrade the Agent Board so you can **draw drag-and-drop lines between agents** (not
just agent->orchestrator). An edge means "this agent's output feeds the next one," so agents
**talk to and reason over each other** — e.g. proposers -> **Fact-checker** -> Orchestrator.
Plus: a big **ECC persona library**.

**Pull from / wire, don't rewrite:**
- Generalize the existing council, don't replace it: `scripts/jarvis_council.py:run_council`
  already does propose->critique->synthesize with laddered streaming + `emit` frames. The graph
  executor is the same call primitive (`complete_with_fallback`/`LiteLLMEngine.stream`) driven
  by a topological order instead of a fixed pipeline.
- React Flow already supports user-drawn edges (`onConnect`) and the existing `PipeEdge`/
  `floatingEdge` — reuse them; just allow agent->agent connections (handles already exist on
  `AgentNode`/`OrchestratorNode`).
- **ECC persona lenses** — pull the real system prompts from the installed agent definitions
  instead of authoring new ones: `~/.claude/agents/*.md` and the ECC plugin agents
  (e.g. `ecc:code-reviewer`, `ecc:security-reviewer`, `ecc:python-reviewer`, ...). Read each
  agent's description/instructions and use it as the persona `lens`. (See Persona Catalog.)

**New backend — `scripts/jarvis_graph.py` (the one new module; reuses everything else):**
- Input: `{task, nodes:[{id,persona,lens,model}], edges:[{source,target}]}`.
- Validate a **DAG** (reject cycles in v1; v2 may allow bounded debate loops with a max-iteration cap).
- **Topological execution:** each node's prompt = `task` + concatenated outputs of its
  upstream (incoming-edge) nodes; system prompt = its lens. Orchestrator = terminal node that
  synthesizes its incoming outputs (reuse `synthesis_directive`).
- **Free-tier guard:** at most **3 LLM calls in flight** (independent nodes run up to the cap,
  dependents wait) — same backoff/ladder as the council, no 429 storm.
- **Frame protocol** (so the board animates): `node_start{node}`, `node_chunk{node,content}`,
  `node_end{node,content,model}`, `edge_flow{source,target}` (pulse that drawn line as data
  passes), `graph_done{output}`, `error{detail}`. Keyed by **node id** (not PROPOSAL index).
- Note: the flat roster council is just the special case "all agents -> orchestrator," so
  `jarvis_graph` subsumes it; keep `run_council` for the CLI.

**Sidecar:** `WS /api/graph` (mirror `council_ws`, forward `{task,nodes,edges}` to `jarvis_graph`).
Extend `/api/board` `board.json` to store inter-agent edges (already has `edges` — relax the
validator so `source`/`target` may be any node id, not just `orchestrator`).

**Frontend (`AgentsTab.jsx` + `board/*`):**
- Enable `onConnect` so dragging from one agent's handle to another's draws a "feeds" edge.
- Switch the board's run path from `boardSocket`(council) to a `graphSocket` on `/api/graph`,
  sending the full `{nodes, edges}` graph; map `node_*` frames by id and pulse `edge_flow` edges.
- Expand `lib/agents.js` with the ECC persona catalog (below); group the palette by category
  (Reviewers / Builders / Architects / Domain / Research) like a real agent drawer.
- Optional edge types later (review / critique / debate) — v1 ships a single "feeds" edge.

**Gate:** draw proposers -> Fact-checker -> Orchestrator; run a task; each node streams in
topological order; the drawn lines pulse as outputs flow; Fact-checker visibly consumes the
proposers' text before the Orchestrator synthesizes; <=3 concurrent calls; layout persists.

---

## Phase 10 · A — Vision & camera

**Goal:** Browser face-auth unlock, hand-gesture control, and a live camera/audio visualizer —
the ada features, as web modules.

**Pull from / wire, don't rewrite:**
- Face auth: `_vendor/ada_v2/backend/{authenticator.py,capture_face.py}` + `src/components/AuthLock.jsx`
  + `src/test_face_rec.py`. ada streams frames over its socket (`server.py:video_frame`,
  `on_auth_frame`) — port that path onto our sidecar (`getUserMedia` -> WS -> recognizer -> unlock).
- Hand gesture: `_vendor/ada_v2/hand_gesture_test.py` (MediaPipe). Stream frames to the sidecar
  or run MediaPipe Hands in-browser; map gestures -> UI actions.
- Visualizer / audio bar: `_vendor/ada_v2/src/components/{Visualizer.jsx,TopAudioBar.jsx}` —
  reuse the existing Phase-6 mic capture (`web/src/lib/voiceSocket.js`, `pcm-worklet.js`).

**Backend:** new `scripts/jarvis_vision.py` wrapping ada's recognizer; `WS /api/vision` for
frame-in / result-out. Reuse Phase-6 audio plumbing for the visualizer.

**Gate:** camera module recognizes an enrolled face and unlocks; a hand gesture triggers a
mapped action; the visualizer reacts to mic/audio in real time.

---

## Phase 11 · D — Action tools + F — Clicky

### D — Web-safe action tools (port Mark-XL / ada agents as orchestrator tools)

**Goal:** Give the orchestrator real capabilities by **registering existing actions as MCP/
router tools** — no reimplementation.

**Pull from / wire, don't rewrite — register these existing modules as tools:**
- Mark-XL `actions/`: `web_search.py`, `weather_report.py`, `youtube_video.py`, `reminder.py`,
  `flight_finder.py`, `file_processor.py`, `screen_processor.py`. (Skip local-machine-control
  ones for a web app: `computer_control`, `desktop`, `open_app`, `send_message` — see appendix.)
- ada `backend/`: `web_agent.py` (web browse/fetch — overlaps existing Agent-Reach),
  `cad_agent.py`/`temp_cad_gen.py` (text->CAD, optional), `kasa_agent.py` (smart home, optional/HW),
  `printer_agent.py` (3D printer, optional/HW), `tools.py` (its tool-spec shapes).

**How:** wrap each as a small MCP tool (mirror the Phase-2 MCP wiring in `setup_config.py` +
`config.tools.mcp.servers`) **or** a thin function tool the router can call. Prefer porting the
function bodies wholesale and only adapting I/O.

**Gate:** orchestrator answers "what's the weather / search X / remind me Y" by invoking the
ported action; a CAD/optional tool runs behind a feature flag.

### F — Clicky ability (screen-aware Q&A + on-screen pointing)

**Goal:** "What's on my screen?" / "Where is X?" -> Jarvis captures the screen, a **vision model**
locates the element, and the web UI shows the screenshot with the spot highlighted (web-native
variant of Clicky's pixel-pointing). Voice push-to-talk + journal optional.

**Pull from / wire, don't rewrite:**
- Clone `https://github.com/Bitshank-2338/clicky-windows.git` -> `_vendor/clicky-windows` (read-only).
  Port its **two-stage grid pointing** prompt + screen-capture + multi-provider client (it already
  supports Claude/OpenAI/Gemini/Ollama — pairs with Phase 7 keys).
- Screen capture also exists in Mark-XL `actions/screen_processor.py` — reuse whichever is cleaner.
- Vision needs a vision-capable model -> **depends on Phase 7** (OpenAI/Claude/Gemini key).

**Backend:** `scripts/jarvis_clicky.py` (port capture + grid-locate); `POST /api/clicky/point`
-> `{question}` -> screenshot -> vision model -> `{description, box:[x,y,w,h], screenshot}`.

**Frontend:** a Clicky module window showing the annotated screenshot + answer; optional
push-to-talk hotkey. (Desktop PyQt overlay from clicky is **out of scope** for the web app;
note it as an optional native add-on.)

**Gate:** ask "where is the Save button" with something on screen -> annotated screenshot with the
correct region highlighted + a spoken/text answer.

---

## Persona Catalog (Phase 9 data — pull lenses from real ECC agents)

Port each into `web/src/lib/agents.js` as `{id, persona, category, defaultModelKey, accent, lens}`.
**Source the `lens` from the agent's real definition** (`~/.claude/agents/<id>.md` or the ECC
plugin agent description) — don't invent prompts. Cap **active proposers at 3** still applies; the
library can be large, the board limits concurrency.

**Already shipped (keep):** Architect, Skeptic, Pragmatist, Coder, Researcher, Creative,
Fact-checker, Planner.

**Add from ECC (representative — include all that have a definition file):**
| id | persona | category | ECC source |
|---|---|---|---|
| code-reviewer | Code Reviewer | Reviewers | `ecc:code-reviewer` / `code-reviewer` |
| security-reviewer | Security Reviewer | Reviewers | `ecc:security-reviewer` |
| python-reviewer | Python Reviewer | Reviewers | `ecc:python-reviewer` |
| typescript-reviewer | TypeScript Reviewer | Reviewers | `ecc:typescript-reviewer` |
| go-reviewer | Go Reviewer | Reviewers | `ecc:go-reviewer` |
| rust-reviewer | Rust Reviewer | Reviewers | `ecc:rust-reviewer` |
| java-reviewer | Java Reviewer | Reviewers | `ecc:java-reviewer` |
| cpp-reviewer | C++ Reviewer | Reviewers | `ecc:cpp-reviewer` |
| database-reviewer | Database Reviewer | Reviewers | `ecc:database-reviewer` |
| silent-failure-hunter | Silent-Failure Hunter | Reviewers | `ecc:silent-failure-hunter` |
| type-design-analyzer | Type-Design Analyst | Reviewers | `ecc:type-design-analyzer` |
| comment-analyzer | Comment Analyst | Reviewers | `ecc:comment-analyzer` |
| pr-test-analyzer | PR Test Analyst | Reviewers | `ecc:pr-test-analyzer` |
| build-error-resolver | Build Fixer | Builders | `build-error-resolver` |
| tdd-guide | TDD Guide | Builders | `ecc:tdd-guide` |
| refactor-cleaner | Refactor Cleaner | Builders | `refactor-cleaner` |
| performance-optimizer | Performance Optimizer | Builders | `ecc:performance-optimizer` |
| code-architect | Code Architect | Architects | `ecc:code-architect` |
| code-explorer | Code Explorer | Architects | `ecc:code-explorer` |
| a11y-architect | Accessibility Architect | Architects | `ecc:a11y-architect` |
| doc-updater | Doc Updater | Architects | `doc-updater` |
| mle-reviewer | ML-Engineering Reviewer | Domain | `ecc:mle-reviewer` |
| seo-specialist | SEO Specialist | Domain | `ecc:seo-specialist` |
| network-architect | Network Architect | Domain | `ecc:network-architect` |
| healthcare-reviewer | Healthcare Reviewer | Domain | `ecc:healthcare-reviewer` |
| explorer | Researcher/Explorer | Research | `Explore` / `general-purpose` |

> Implementation tip: write a tiny build-time script that reads `~/.claude/agents/*.md`,
> extracts each agent's name + description as `{persona, lens}`, and emits the catalog — so
> the personas literally **come from the existing agent definitions**, staying in sync.

---

## Feature-parity appendix — every ada_v2 + Mark-XL feature (nothing missed)

Disposition: **PORT** (wire as-is), **WEB** (port with a browser-native variant),
**FLAG** (port behind a feature flag / needs hardware), **SKIP** (local-machine control unsafe
for a web app — document, don't silently drop).

### ada_v2
| Feature | Files | Disposition | Phase |
|---|---|---|---|
| Face-recognition auth | `backend/authenticator.py`, `capture_face.py`, `src/AuthLock.jsx`, `test_face_rec.py` | WEB | A |
| Hand-gesture control | `hand_gesture_test.py` | WEB | A |
| Audio visualizer / top bar | `src/Visualizer.jsx`, `TopAudioBar.jsx` | PORT | A/C |
| Window/module shell | `src/App.jsx`, `*Window.jsx`, `ChatModule.jsx`, `ToolsModule.jsx` | PORT | C |
| Confirmation popups / memory prompt | `src/ConfirmationPopup.jsx`, `MemoryPrompt.jsx` | PORT | C |
| Web agent (browse/fetch) | `backend/web_agent.py`, `src/BrowserWindow.jsx` | WEB (overlaps Agent-Reach) | D |
| CAD generation (text->STL) | `backend/cad_agent.py`, `temp_cad_gen.py`, `verify_cad.py`, `src/CadWindow.jsx` | FLAG | D |
| Kasa smart-home | `backend/kasa_agent.py`, `src/KasaWindow.jsx` | FLAG (HW) | D |
| 3D-printer control | `backend/printer_agent.py`, `src/PrinterWindow.jsx` | FLAG (HW) | D |
| Settings persistence | `backend/server.py` `load/save_settings` | PORT | E/C |
| Tool-spec shapes | `backend/tools.py`, `project_manager.py` | PORT (reference) | D |

### Mark-XL (`actions/`)
| Feature | File | Disposition | Phase |
|---|---|---|---|
| Web search | `web_search.py` | PORT | D |
| Weather | `weather_report.py` | PORT | D |
| YouTube (play/summarize/info/trending) | `youtube_video.py` | WEB | D |
| Reminders | `reminder.py` | PORT | D |
| Flight finder | `flight_finder.py` | PORT | D |
| File processing | `file_processor.py` | PORT | D |
| Screen processing/capture | `screen_processor.py` | PORT (also feeds Clicky) | D/F |
| Code helper / dev agent | `code_helper.py`, `dev_agent.py` | PORT (or supersede w/ personas) | D |
| STT / TTS / planner / executor | `core/{stt,tts}.py`, `agent/{planner,executor,task_queue}.py` | DONE (Phase 6) / reference | — |
| Browser control (Selenium) | `browser_control.py` | WEB (Playwright already present) | D |
| Computer control / desktop / open app | `computer_control.py`, `desktop.py`, `open_app.py` | SKIP for web (local-machine control); optional native add-on, document risk | — |
| Send message / computer settings / game updater | `send_message.py`, `computer_settings.py`, `game_updater.py` | SKIP/FLAG (local + risk) | — |

### Clicky
| Feature | Disposition | Phase |
|---|---|---|
| Screen-aware Q&A + pixel pointing | WEB (annotated screenshot) | F |
| Multi-provider LLM client | PORT (pairs with Phase 7) | F |
| Knowledge journal (SQLite + spaced repetition) | FLAG (optional) | F |
| Document drag-drop context | WEB (optional) | F |
| Push-to-talk + lesson MP4 recording | FLAG (optional native) | F |

---

## Hard rules recap (apply to every phase)
- **Pull from existing code; never reimplement** a feature a vendor repo already provides.
- No backbone/`_vendor` edits; wire through `jarvis_web_api.py` + the Phase-1 router.
- Never hardcode a model id — all ids from `.env`. Never echo a secret; `.env` is user-owned.
- No browser `localStorage` — persist via sidecar JSON endpoints (pattern: `/api/board`).
- Council/graph: <=3 concurrent LLM calls; exponential backoff + NIM->Gemini->local ladder.
- Windows / PowerShell; `PYTHONUTF8=1`. Tests >=80% on new code; one gate per phase.
