<#
.SYNOPSIS
    Bring the full AI-Amooz stack up locally (Windows / PowerShell).

.DESCRIPTION
    Builds and starts the backend stack in Docker (postgres, redis, minio,
    backend, celery-worker), runs database migrations, then starts the
    Next.js frontend dev server on http://localhost:9002.

    Run from anywhere:
        powershell -ExecutionPolicy Bypass -File scripts\dev-up.ps1

.PARAMETER NoFrontend
    Start only the Docker backend stack; skip the frontend dev server.

.PARAMETER Superuser
    Create a Django superuser interactively after migrations.
#>
param(
    [switch]$NoFrontend,
    [switch]$Superuser
)

$ErrorActionPreference = "Stop"

# --- Resolve repo root (this script lives in <root>\scripts) -----------------
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
Write-Host "Repo root: $RepoRoot" -ForegroundColor DarkGray

# --- Pick the right compose command (v2 'docker compose' vs v1) --------------
function Get-Compose {
    try { docker compose version *> $null; if ($LASTEXITCODE -eq 0) { return ,@("docker","compose") } } catch {}
    try { docker-compose version *> $null; if ($LASTEXITCODE -eq 0) { return ,@("docker-compose") } } catch {}
    throw "Docker Compose not found. Is Docker Desktop running?"
}
$Compose      = Get-Compose
$ComposeExe   = $Compose[0]
$ComposeArgs  = @(); if ($Compose.Count -gt 1) { $ComposeArgs = $Compose[1..($Compose.Count - 1)] }
function Compose { & $ComposeExe @ComposeArgs @args }

# --- Verify Docker daemon is up ----------------------------------------------
Write-Host "==> Checking Docker daemon..." -ForegroundColor Cyan
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker daemon is not reachable. Start Docker Desktop and retry." }

# --- Build images ------------------------------------------------------------
Write-Host "==> Building images (this can take a few minutes the first time)..." -ForegroundColor Cyan
Compose build

# --- Start infrastructure first ----------------------------------------------
Write-Host "==> Starting postgres, redis, minio..." -ForegroundColor Cyan
Compose up -d postgres redis minio minio-init

# --- Wait for Postgres to be healthy -----------------------------------------
Write-Host "==> Waiting for Postgres to become healthy..." -ForegroundColor Cyan
$healthy = $false
for ($i = 1; $i -le 30; $i++) {
    Start-Sleep -Seconds 3
    $status = (docker inspect -f '{{.State.Health.Status}}' ai_amooz_postgres 2>$null)
    Write-Host ("    [{0,2}/30] postgres: {1}" -f $i, $status)
    if ($status -eq "healthy") { $healthy = $true; break }
}
if (-not $healthy) { throw "Postgres did not become healthy in time. Check: $($Compose -join ' ') logs postgres" }

# --- Migrations + cache table ------------------------------------------------
Write-Host "==> Applying database migrations..." -ForegroundColor Cyan
Compose run --rm backend python manage.py migrate
if ($LASTEXITCODE -ne 0) { throw "Migrations failed. Inspect: $ComposeExe $($ComposeArgs -join ' ') logs backend" }

Write-Host "==> Ensuring cache table (harmless if using Redis cache)..." -ForegroundColor Cyan
try { Compose run --rm backend python manage.py createcachetable } catch { Write-Host "    (skipped: $($_.Exception.Message))" -ForegroundColor DarkYellow }

if ($Superuser) {
    Write-Host "==> Creating Django superuser..." -ForegroundColor Cyan
    Compose run --rm backend python manage.py createsuperuser
}

# --- Start the application services -------------------------------------------
Write-Host "==> Starting backend + celery worker..." -ForegroundColor Cyan
Compose up -d backend celery-worker

Write-Host ""
Write-Host "==> Stack status:" -ForegroundColor Green
Compose ps

Write-Host ""
Write-Host "Backend API : http://localhost:8000/api/"      -ForegroundColor Green
Write-Host "API docs    : http://localhost:8000/api/docs/" -ForegroundColor Green
Write-Host "Django admin: http://localhost:8000/admin/"    -ForegroundColor Green
Write-Host "MinIO       : http://localhost:9001  (minioadmin / minioadmin)" -ForegroundColor Green
Write-Host ""

if ($NoFrontend) {
    Write-Host "Backend stack is up. Skipping frontend (-NoFrontend)." -ForegroundColor Yellow
    Write-Host "Start it later with:  cd frontend ; npm run dev   ->  http://localhost:9002"
    return
}

# --- Frontend dev server (blocking; keep this terminal open) ------------------
Write-Host "==> Preparing frontend..." -ForegroundColor Cyan
Set-Location (Join-Path $RepoRoot "frontend")
if (-not (Test-Path "node_modules")) {
    Write-Host "    Installing npm dependencies..."
    npm install
}
Write-Host "==> Starting Next.js dev server on http://localhost:9002 (Ctrl+C to stop)..." -ForegroundColor Green
npm run dev
