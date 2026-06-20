# bootstrap.ps1 — Jarvis: empty folder -> ready for Phase 0
# Windows / PowerShell.
#
# PREREQS (run once in a separate window, THEN open a fresh window before running this script):
#   winget install --id Git.Git -e
#   winget install --id Python.Python.3.12 -e
#   winget install --id OpenJS.NodeJS.LTS -e
#   winget install --id Ollama.Ollama -e
#   powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
#
# RUN:  powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1

param([string]$Root = "C:\Users\bhavy\Desktop\projectfiles")

$ErrorActionPreference = "Stop"
# $Root defaults to your desktop projectfiles folder; override with: .\bootstrap.ps1 -Root "D:\elsewhere"

Write-Host "==> Project root: $Root" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $Root | Out-Null
Set-Location $Root

Write-Host "==> Cloning OpenJarvis (backbone) into project root" -ForegroundColor Cyan
if (-not (Test-Path ".git")) {
    git clone https://github.com/open-jarvis/OpenJarvis.git .
} else {
    Write-Host "    already a git repo here, skipping clone" -ForegroundColor DarkGray
}

Write-Host "==> Cloning reference repos into _vendor/ (read-only source)" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path "_vendor" | Out-Null
$refs = [ordered]@{
    "codebase-memory-mcp" = "https://github.com/DeusData/codebase-memory-mcp.git"
    "Agent-Reach"         = "https://github.com/Panniantong/Agent-Reach.git"
    "superpowers"         = "https://github.com/obra/superpowers.git"
    "ada_v2"              = "https://github.com/nazirlouis/ada_v2.git"
    "Mark-XL"             = "https://github.com/FatihMakes/Mark-XL.git"
}
foreach ($name in $refs.Keys) {
    $dest = "_vendor/$name"
    if (Test-Path $dest) { Write-Host "    $name exists, skipping" -ForegroundColor DarkGray; continue }
    git clone --depth 1 $refs[$name] $dest
}

Write-Host "==> Updating .gitignore (keep _vendor, secrets, venvs out of git)" -ForegroundColor Cyan
@"

# --- Jarvis additions ---
_vendor/
.env
.venv/
__pycache__/
node_modules/
web/node_modules/
*.log
"@ | Out-File -FilePath ".gitignore" -Encoding utf8 -Append

Write-Host "==> Installing OpenJarvis from source (editable) via uv" -ForegroundColor Cyan
uv python install 3.12
try {
    uv sync
} catch {
    Write-Host "    uv sync failed (likely a Linux/GPU-only optional dep such as vllm)." -ForegroundColor Yellow
    Write-Host "    This build only needs litellm + ollama + server + agents — see OpenJarvis Windows" -ForegroundColor Yellow
    Write-Host "    install notes to install without that optional group, then re-run this script." -ForegroundColor Yellow
    throw
}

Write-Host "==> Pulling a small local fallback model via Ollama (fits 8 GB)" -ForegroundColor Cyan
ollama pull qwen2.5:7b

Write-Host "==> Writing .env template (EDIT IT — paste real keys in the file, not the terminal)" -ForegroundColor Cyan
if (-not (Test-Path ".env")) {
@"
# NVIDIA NIM — free nvapi- key at https://build.nvidia.com
NVIDIA_API_KEY=nvapi-REPLACE_ME
# Gemini Flash — second voice / fallback
GEMINI_API_KEY=REPLACE_ME

# Model routing (VERIFY current IDs at build.nvidia.com — they drift monthly)
NIM_MODEL_REASONING=nvidia/llama-3.3-nemotron-super-49b-v1
NIM_MODEL_CODE=qwen/qwen3-coder-480b-a35b-instruct
NIM_MODEL_GENERAL=meta/llama-3.3-70b-instruct
NIM_COUNCIL_1=meta/llama-3.3-70b-instruct
NIM_COUNCIL_2=qwen/qwen3-coder-480b-a35b-instruct
NIM_COUNCIL_3=deepseek-ai/deepseek-r1
NIM_CRITIC=nvidia/llama-3.3-nemotron-super-49b-v1
GEMINI_FALLBACK_MODEL=gemini/gemini-2.0-flash
LOCAL_FALLBACK_MODEL=ollama/qwen2.5:7b
"@ | Out-File -FilePath ".env" -Encoding utf8
} else {
    Write-Host "    .env already exists, leaving it alone" -ForegroundColor DarkGray
}

Write-Host "==> Sanity check: OpenJarvis CLI" -ForegroundColor Cyan
uv run jarvis --help

Write-Host ""
Write-Host "DONE." -ForegroundColor Green
Write-Host "Next:" -ForegroundColor Yellow
Write-Host "  1) Open .env and paste your real NVIDIA_API_KEY and GEMINI_API_KEY." -ForegroundColor Yellow
Write-Host "  2) In Cursor: paste the Global Rules, then run the Phase 0 prompt." -ForegroundColor Yellow
Write-Host "     (Bootstrap already did Phase 0 steps 1-2; Cursor starts at the NIM config wiring.)" -ForegroundColor Yellow
