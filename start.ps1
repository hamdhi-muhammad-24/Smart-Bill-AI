# start.ps1 — One-command startup for SLT Billing System
# Usage:
#   .\start.ps1           — start all services
#   .\start.ps1 --setup   — run DB migrations + seed first, then start all

param(
    [switch]$setup
)

$ProjectRoot = $PSScriptRoot
$VenvPython = "$ProjectRoot\.venv\Scripts\python.exe"

Write-Host ""
Write-Host "=== SLT Billing System — Starting Up ===" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: DB setup (optional) ───────────────────────────────────────────────
if ($setup) {
    Write-Host "[--setup] Running DB migrations and seed..." -ForegroundColor Yellow
    Set-Location $ProjectRoot

    if (Test-Path $VenvPython) {
        & $VenvPython -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: alembic upgrade failed." -ForegroundColor Red; exit 1 }

        & $VenvPython -m app.db.seed
        if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: app.db.seed failed." -ForegroundColor Red; exit 1 }
    } else {
        uv run alembic upgrade head
        if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: alembic upgrade failed." -ForegroundColor Red; exit 1 }

        uv run python -m app.db.seed
        if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: app.db.seed failed." -ForegroundColor Red; exit 1 }
    }

    Write-Host "      DB ready." -ForegroundColor Green
    Write-Host ""
}

# ── Step 2: FastAPI backend (new window) ──────────────────────────────────────
Write-Host "[1/3] Starting FastAPI backend on http://localhost:8090 ..." -ForegroundColor Yellow
$stale_api = (Get-NetTCPConnection -LocalPort 8090 -ErrorAction SilentlyContinue).OwningProcess
if ($stale_api) {
    Write-Host "      Killing stale process on port 8090 (PID $stale_api)..." -ForegroundColor DarkGray
    Stop-Process -Id $stale_api -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
}
$BackendCmd = if (Test-Path $VenvPython) { "& '$VenvPython' -m uvicorn app.api.main:app --reload --port 8090" } else { "uv run uvicorn app.api.main:app --reload --port 8090" }
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$ProjectRoot'; $BackendCmd"
) -WindowStyle Normal
Write-Host "      FastAPI window opened." -ForegroundColor Green
Write-Host ""

# ── Step 3: React frontend (new window) ───────────────────────────────────────
Write-Host "[2/3] Starting React frontend on http://localhost:5173 ..." -ForegroundColor Yellow
$stale = (Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue).OwningProcess
if ($stale) {
    Write-Host "      Killing stale process on port 5173 (PID $stale)..." -ForegroundColor DarkGray
    Stop-Process -Id $stale -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
}
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$ProjectRoot\frontend'; npm run dev"
) -WindowStyle Normal
Write-Host "      React window opened." -ForegroundColor Green
Write-Host ""

# ── Step 4: Background Worker Queue (new window) ──────────────────────────────
Write-Host "[4/4] Starting Async Background Worker Queue ..." -ForegroundColor Yellow
$WorkerCmd = if (Test-Path $VenvPython) { "& '$VenvPython' -m app.billing.worker_queue" } else { "uv run python -m app.billing.worker_queue" }
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$ProjectRoot'; $WorkerCmd"
) -WindowStyle Normal
Write-Host "      Worker queue window opened." -ForegroundColor Green
Write-Host ""

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host "=== All services starting ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Frontend   ->  http://localhost:5173" -ForegroundColor White
Write-Host "  API        ->  http://localhost:8090" -ForegroundColor White
Write-Host "  API Docs   ->  http://localhost:8090/docs" -ForegroundColor White
Write-Host ""
Write-Host "Wait ~5 seconds for the frontend to compile, then open your browser." -ForegroundColor DarkGray
Write-Host ""
