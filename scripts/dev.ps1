$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$FrontendDir = Join-Path $Root "frontend"
$EnvFile = Join-Path $Root ".env"
$FrontendEnvFile = Join-Path $FrontendDir ".env"

if (-not (Test-Path $EnvFile)) {
  Write-Warning "Root .env not found. Copy .env.example to .env and fill ZHIPUAI_API_KEY before using chat APIs."
}

if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
  Write-Warning "frontend/node_modules not found. Run: npm --prefix frontend install"
}

if (-not (Test-Path $FrontendEnvFile)) {
  Write-Host "frontend/.env not found; Vite will use the built-in /api proxy." -ForegroundColor Yellow
}

Write-Host "Starting FastAPI backend at http://127.0.0.1:8000 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-Command",
  "Set-Location `"$Root`"; python backend/main.py"
)

Write-Host "Starting Vue frontend at http://localhost:3000 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-Command",
  "Set-Location `"$FrontendDir`"; npm run dev"
)

Write-Host ""
Write-Host "Health check: http://127.0.0.1:8000/api/health" -ForegroundColor Green
Write-Host "Frontend:     http://localhost:3000" -ForegroundColor Green
