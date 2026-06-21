<div align="center">

# 🤖 Jarvis — Agentic Multi-Model Orchestrator

**One "head" that routes every task to the best model, convenes a multi-model planning council for hard problems, remembers what matters, calls real tools over MCP, and talks back — all running locally on Windows.**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-sidecar-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-Web%20UI-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![LiteLLM](https://img.shields.io/badge/LiteLLM-engine-6E56CF)](https://github.com/BerriAI/litellm)
[![NVIDIA NIM](https://img.shields.io/badge/NVIDIA-NIM-76B900?logo=nvidia&logoColor=white)](https://build.nvidia.com/)
[![MCP](https://img.shields.io/badge/MCP-tools-FF6B6B)](https://modelcontextprotocol.io/)
[![Tests](https://img.shields.io/badge/web%20tests-24%2F24-success)](#-testing)

</div>

---

## ✨ What is this?

Jarvis is a **local agentic orchestrator** built on the [OpenJarvis](https://github.com/open-jarvis/OpenJarvis) backbone. It wires together six proven open-source capabilities into a single assistant with one design principle: **integrate and configure — don't reimplement.**

It picks the right model per task, escalates hard planning questions to a **3-model council**, keeps durable memory, drops in **MCP tools** (a live code-graph + web/GitHub access), and supports **always-on voice** — behind a clean 7-tab web UI.

| | |
|---|---|
| 🧠 **Smart routing** | Classifies each task (code / reasoning / general) and routes to the best NVIDIA NIM model |
| 🪜 **Resilient fallback** | `NIM-A → NIM-B → Gemini → local Ollama` with exponential backoff + 429 handling |
| 🏛️ **Planning council** | 3 distinct models propose in parallel → a reasoning model critiques → synthesizes one plan |
| 💾 **Memory** | Durable personal facts, session history, and a queryable code graph |
| 🔌 **MCP tools** | Codebase-Memory graph (`:9749`) + Agent-Reach web/GitHub fetch, dropped in via config |
| 🎙️ **Voice** | Browser mic → wake word → STT → orchestrator → TTS, with barge-in |

---

## 📸 Screenshots

### Chat — streamed answers tagged with the model that served them
> Every reply shows the rung that produced it (`served by NIM-A`).

![Chat](docs/screenshots/chat.png)

### Council — three models think in parallel, then synthesize
> Pragmatist (Llama-3.3-70B), Architect (Qwen3.5-397B) and Skeptic (DeepSeek-V4) each draft a proposal; a reasoning model critiques and merges them.

![Council](docs/screenshots/council.png)

### Connections — live code graph + routing map
> The Codebase-Memory MCP graph (241 nodes / 402 edges of this very repo) alongside the live NIM fallback ladders.

![Connections](docs/screenshots/connections.png)

<table>
<tr>
<td width="50%">

**Voice — always-on wake word**

![Voice](docs/screenshots/voice.png)

</td>
<td width="50%">

**Memory — durable personal facts**

![Memory](docs/screenshots/memory.png)

</td>
</tr>
<tr>
<td width="50%">

**Tools — drop-in MCP servers**

![Tools](docs/screenshots/tools.png)

</td>
<td width="50%">

**Settings — switch models without restart**

![Settings](docs/screenshots/settings.png)

</td>
</tr>
</table>

---

## 🏗️ Architecture

A thin **FastAPI sidecar** (`:8700`) bridges the React web UI to the Jarvis "brain" — every LLM call flows through OpenJarvis's LiteLLM engine, with **zero edits to the backbone or vendored repos**.

```mermaid
flowchart TB
    subgraph Browser["Browser - React + Vite (:5173)"]
        Chat["Chat"]
        Voice["Voice (16 kHz PCM worklet)"]
        Council["Council"]
        Graph["Connections"]
        Mem["Memory"]
        Tools["Tools"]
    end

    subgraph Sidecar["FastAPI Sidecar (:8700) - thin glue, no backbone edits"]
        WSChat["WS /api/chat"]
        WSVoice["WS /api/voice"]
        WSCouncil["WS /api/council"]
        REST["REST /api/memory, /api/routing, /api/mcp"]
    end

    subgraph Brain["Jarvis Brain (reused OpenJarvis + scripts)"]
        Router["Router + Fallback Ladder"]
        CouncilEng["Planning Council"]
        Memory["Memory (facts, session, code graph)"]
        VoiceEng["Voice (wake, STT, TTS)"]
        Engine["LiteLLM Engine"]
    end

    subgraph Models["Models"]
        NIM["NVIDIA NIM (primary + council)"]
        Gemini["Gemini Flash (fallback)"]
        Ollama["Ollama qwen2.5:7b (offline)"]
    end

    subgraph MCP["MCP Servers"]
        CBM["Codebase-Memory graph :9749"]
        AR["Agent-Reach web / GitHub"]
    end

    Chat --> WSChat --> Router
    Voice --> WSVoice --> VoiceEng --> Router
    Council --> WSCouncil --> CouncilEng
    Graph --> REST
    Mem --> REST
    Tools --> REST
    REST --> Memory
    REST --> MCP

    Router --> Engine
    CouncilEng --> Engine
    Engine --> NIM
    Engine -.fallback.-> Gemini
    Engine -.offline.-> Ollama
    Memory --> CBM
    REST --> AR
```

### Request routing & the fallback ladder

Each prompt is classified by keyword heuristics, mapped to a role model, then run through a resilient ladder. A per-rung retry with exponential backoff (`1s → 2s → 4s`) absorbs NIM's free-tier `429`s before walking to the next provider — so a single request degrades gracefully instead of failing.

```mermaid
flowchart LR
    P["Prompt"] --> C{classify}
    C -->|code| CM["Qwen3.5-397B"]
    C -->|reasoning| RM["Nemotron-49B"]
    C -->|general| GM["Llama-3.3-70B"]

    CM --> L
    RM --> L
    GM --> L

    subgraph L["Fallback Ladder (per request)"]
        direction LR
        A["NIM-A role model"] -->|429 / timeout| B["NIM-B other NIM"]
        B -->|exhausted| G["Gemini Flash"]
        G -->|no key / down| O["Ollama (offline)"]
    end

    L --> R["Answer + 'served by' rung"]
```

### Planning council (hard problems only)

```mermaid
sequenceDiagram
    participant U as User
    participant C as Council
    participant M1 as Pragmatist - Llama-70B
    participant M2 as Architect - Qwen3.5
    participant M3 as Skeptic - DeepSeek-V4
    participant R as Reasoner - Nemotron
    U->>C: "Design X"
    par 3 distinct models, 3 lenses
        C->>M1: propose
        C->>M2: propose
        C->>M3: propose
    end
    M1-->>C: proposal 1
    M2-->>C: proposal 2
    M3-->>C: proposal 3
    C->>R: critique all three (enable_thinking)
    R-->>C: critique
    C->>R: synthesize one plan
    R-->>C: final plan
    C->>U: stream every voice live
```

### Voice pipeline (always-on, barge-in)

```mermaid
flowchart LR
    Mic["getUserMedia"] --> WL["PCM worklet: Float32 to Int16 @ 16 kHz"]
    WL -->|80 ms frames over WS| WW{"openWakeWord 'hey jarvis'"}
    WW -->|score >= 0.5| VAD["webrtcvad segment utterance"]
    VAD --> STT["faster-whisper small / CPU"]
    STT --> ROUTER["Router (same brain as chat)"]
    ROUTER --> TTS["Edge-TTS sentence-streamed mp3"]
    TTS -->|playback| Mic
    Mic -.talk over reply.-> Cancel["barge-in: stop playback"]
```

---

## 🧰 Tech stack

**Orchestration & backend:** Python 3.12 · FastAPI · WebSockets · [LiteLLM](https://github.com/BerriAI/litellm) · [OpenJarvis](https://github.com/open-jarvis/OpenJarvis) backbone
**Models:** NVIDIA NIM (Llama-3.3-70B, Qwen3.5-397B, Nemotron-49B, DeepSeek-V4) · Google Gemini Flash · Ollama (qwen2.5:7b)
**Voice:** openWakeWord · faster-whisper · Edge-TTS · webrtcvad · Web Audio `AudioWorklet`
**Tools:** Model Context Protocol — Codebase-Memory MCP (code graph) · Agent-Reach (web/GitHub)
**Frontend:** React · Vite · Tailwind CSS · Framer Motion · lucide-react — an *ada_v2*-inspired "arc-reactor" HUD (Orbitron / Rajdhani / Share Tech Mono)
**Tooling:** `uv` (deps) · `pytest` (24 web tests) · Playwright (browser smoke)

---

## 🚀 Getting started

> Windows + PowerShell. Assumes `git`, [`uv`](https://docs.astral.sh/uv/), `node`, and [`ollama`](https://ollama.com/) are installed.

```powershell
# 1. Install Python deps (core + extras)
uv sync --extra inference-litellm --extra server --extra inference-google --extra inference-cloud

# 2. Voice deps (one-time)
uv pip install faster-whisper edge-tts openwakeword onnxruntime webrtcvad sounddevice "setuptools<81"
uv run python -c "import openwakeword.utils as u; u.download_models()"

# 3. Local fallback model
ollama pull qwen2.5:7b

# 4. Frontend deps
cd web; npm install; cd ..
```

Create a **`.env`** in the project root (never committed — it's gitignored):

```dotenv
NVIDIA_API_KEY=nvapi-...            # free at build.nvidia.com
GEMINI_API_KEY=...                  # optional fallback
NIM_MODEL_REASONING=nvidia/llama-3.3-nemotron-super-49b-v1
NIM_MODEL_CODE=qwen/qwen3.5-397b-a17b
NIM_MODEL_GENERAL=meta/llama-3.3-70b-instruct
NIM_COUNCIL_1=meta/llama-3.3-70b-instruct
NIM_COUNCIL_2=qwen/qwen3.5-397b-a17b
NIM_COUNCIL_3=deepseek-ai/deepseek-v4-pro
NIM_CRITIC=nvidia/llama-3.3-nemotron-super-49b-v1
GEMINI_FALLBACK_MODEL=gemini/gemini-2.0-flash
LOCAL_FALLBACK_MODEL=ollama/qwen2.5:7b
WAKE_MODEL=hey_jarvis
TTS_VOICE=en-US-GuyNeural
```

> ⚠️ NIM model IDs drift monthly. Run `uv run python scripts/verify_models.py` to validate your IDs against the live `/v1/models` catalog.

### Run it

```powershell
# Web UI + voice (sidecar :8700 + Vite :5173)
pwsh .\scripts\jarvis_web.ps1

# (optional) code-graph UI for the Connections tab
codebase-memory-mcp --ui=true --port=9749

# CLI one-shot
pwsh .\scripts\jarvis.ps1 ask "explain async/await in one paragraph"
```

Open **http://localhost:5173** → Chat round-trips through NIM; Voice tab → *Start always-on* → say **"Hey Jarvis"**.

---

## 🧪 Testing

```powershell
uv run pytest tests/web/ -q                       # 24 sidecar / voice / wake tests
cd web; npx playwright test                        # browser render smoke (launcher must be running)
uv run python scripts/jarvis_router.py doctor      # provider health + per-task model map
```

---

## 📁 Project structure

```text
Jarvis/
├── src/openjarvis/             # OpenJarvis backbone (engine, server, memory, MCP loader)
│   ├── engine/litellm.py       #   unified LLM access (every call goes through here)
│   └── server/cloud_router.py  #   + NVIDIA NIM provider (mirrors existing providers)
├── scripts/                    # the Jarvis orchestration layer (this project's work)
│   ├── jarvis_router.py        #   classify -> route -> fallback ladder -> doctor
│   ├── jarvis_council.py       #   propose x3 -> critique -> synthesize -> execute
│   ├── jarvis_memory.py        #   personal facts (-> USER.md), session, code graph
│   ├── jarvis_voice.py         #   STT (faster-whisper) + TTS (Edge-TTS) glue
│   ├── jarvis_wake.py          #   openWakeWord + webrtcvad segmenter
│   ├── jarvis_web_api.py       #   FastAPI sidecar — wires it all to the browser
│   ├── setup_config.py         #   .env -> ~/.openjarvis/config.toml (+ MCP servers)
│   └── verify_*.py             #   gate checks (models, MCP, memory)
├── web/                        # React UI (ada_v2 fork, Electron stripped)
│   ├── src/components/         #   Chat, Voice, Council, Graph, Memory, Tools, Settings
│   └── src/lib/                #   chatSocket, voiceSocket, pcm-worklet
├── tests/web/                  # pytest: sidecar, voice, wake
├── docs/screenshots/           # the images above
└── PROGRESS.md                 # phase-by-phase build log
```

---

## 🛤️ How it was built

Built in **8 gated phases**, each with a concrete acceptance gate before moving on — the full log lives in [`PROGRESS.md`](PROGRESS.md).

| Phase | Capability | Highlight |
|------:|------------|-----------|
| −1 | Bootstrap | OpenJarvis backbone + 5 reference repos, reproducible `uv` env |
| 0 | NIM wiring | Wired NVIDIA NIM via LiteLLM's native provider; caught 3 drifted model IDs |
| 1 | Router + fallback | Task classifier + `NIM→Gemini→local` ladder with 429-aware backoff |
| 2 | MCP drop-in | Code-graph (`:9749`, 31k nodes) + Agent-Reach, via config only |
| 3 | Memory | Durable facts injected into the system prompt; live cross-turn recall |
| 4 | Council | 3 distinct models + reasoning critic/synthesizer, no 429 storm |
| 5 | Web UI | 7-tab React app over a thin sidecar — zero backbone edits |
| 6 | Voice | Browser mic → wake → STT → orchestrator → TTS, with barge-in |

**Design constraints honored throughout:** never hardcode a model ID (all from `.env`), every LLM call through the LiteLLM engine, and never reimplement what a vendored repo already provides.

---

## 🙏 Credits

This project **integrates** (does not fork-and-rewrite) these open-source projects:

- [**OpenJarvis**](https://github.com/open-jarvis/OpenJarvis) — the orchestration backbone ([upstream README](README.openjarvis.md))
- [**codebase-memory-mcp**](https://github.com/DeusData/codebase-memory-mcp) — code graph + 3D viz over MCP
- [**Agent-Reach**](https://github.com/Panniantong/Agent-Reach) — internet + GitHub access
- [**ada_v2**](https://github.com/nazirlouis/ada_v2) — React web UI shell + voice
- [**Mark-XL**](https://github.com/FatihMakes/Mark-XL) — personal-facts memory + local STT/TTS
- [**superpowers**](https://github.com/obra/superpowers) — development methodology

Model access via [NVIDIA NIM](https://build.nvidia.com/), [Google Gemini](https://ai.google.dev/), and [Ollama](https://ollama.com/).

---

<div align="center">
<sub>Built as a personal/prototype-scale agentic orchestrator. Vendored repos are referenced under their own licenses.</sub>
</div>
