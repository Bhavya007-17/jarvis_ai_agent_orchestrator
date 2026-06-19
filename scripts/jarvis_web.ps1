# scripts/jarvis_web.ps1 - start the Jarvis Web UI (sidecar + Vite)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

# Load .env into the process (KEY=VALUE lines), mirror NVIDIA_API_KEY for LiteLLM nvidia_nim
Get-Content (Join-Path $root ".env") | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
    }
}
if ($env:NVIDIA_API_KEY -and -not $env:NVIDIA_NIM_API_KEY) { $env:NVIDIA_NIM_API_KEY = $env:NVIDIA_API_KEY }
$env:PYTHONUTF8 = "1"

Write-Host "Starting sidecar on :8700 ..." -ForegroundColor Cyan
$sidecar = Start-Process -PassThru -NoNewWindow uv `
    -ArgumentList "run","uvicorn","jarvis_web_api:app","--app-dir","scripts","--port","8700"

Write-Host "Starting Vite dev server on :5173 ..." -ForegroundColor Cyan
Push-Location (Join-Path $root "web")
try { npm run dev } finally {
    Pop-Location
    if ($sidecar -and -not $sidecar.HasExited) { Stop-Process -Id $sidecar.Id -Force }
}
