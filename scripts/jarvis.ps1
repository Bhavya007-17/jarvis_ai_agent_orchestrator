# scripts/jarvis.ps1 - Jarvis launcher.
# The OpenJarvis CLI does NOT auto-load .env, and the engine/LiteLLM path reads keys from
# os.environ. This wrapper loads .env into the process env, maps NVIDIA_API_KEY ->
# NVIDIA_NIM_API_KEY (LiteLLM's native nvidia_nim/ provider), then runs the CLI. Keeps .env
# the single source of truth for keys + model IDs.
#
# No param() block on purpose: a declared parameter set makes PowerShell try to bind short
# flags like -e/-m to the script (ambiguous with -ErrorAction). Using the automatic $args
# passes every token straight through to the CLI.
#
# Usage:
#   .\scripts\jarvis.ps1 ask "hello"
#   .\scripts\jarvis.ps1 ask -e ollama -m qwen2.5:7b "hello"   # offline fallback
#   .\scripts\jarvis.ps1 doctor
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith("#") -or ($t -notmatch "=")) { continue }
        $parts = $t.Split("=", 2)
        $k = $parts[0].Trim(); $v = $parts[1].Trim()
        if ($v -and ($v -notmatch "REPLACE_ME")) { Set-Item -Path "Env:$k" -Value $v }
    }
}
# LiteLLM's native nvidia_nim provider authenticates with NVIDIA_NIM_API_KEY.
if ($env:NVIDIA_API_KEY -and -not $env:NVIDIA_NIM_API_KEY) { $env:NVIDIA_NIM_API_KEY = $env:NVIDIA_API_KEY }
# Phase 2: MCP stdio servers are spawned with text=True, which decodes via the
# parent locale (cp1252 on Windows). Agent-Reach's status output contains emoji
# and CJK, so force Python UTF-8 mode here — otherwise tool output raises a
# 'charmap' decode error. Fixes the integration without patching OpenJarvis.
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
Set-Location $root
& uv run jarvis @args
