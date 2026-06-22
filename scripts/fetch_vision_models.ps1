# scripts/fetch_vision_models.ps1
# Download MediaPipe Tasks Vision wasm + models into web/public/mediapipe so the
# app runs offline (no runtime CDN dependency). Gitignored binary assets.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dest = Join-Path $root "web/public/mediapipe"
$wasm = Join-Path $dest "wasm"
New-Item -ItemType Directory -Force -Path $wasm | Out-Null

$models = @{
  "face_landmarker.task" = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
  "hand_landmarker.task" = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
}
foreach ($name in $models.Keys) {
  $out = Join-Path $dest $name
  Write-Host "[vision] downloading $name ..."
  Invoke-WebRequest -Uri $models[$name] -OutFile $out
}

# WASM runtime files from the installed npm package.
$pkgWasm = Join-Path $root "web/node_modules/@mediapipe/tasks-vision/wasm"
if (Test-Path $pkgWasm) {
  Copy-Item -Path (Join-Path $pkgWasm "*") -Destination $wasm -Recurse -Force
  Write-Host "[vision] copied wasm runtime from node_modules"
} else {
  Write-Host "[vision] WARN: $pkgWasm not found - run 'npm install' in web/ first"
}
Write-Host "[vision] done -> $dest"
