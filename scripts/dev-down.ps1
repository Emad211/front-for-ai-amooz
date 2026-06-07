<#
.SYNOPSIS
    Stop the AI-Amooz local stack.

.DESCRIPTION
    Stops and removes the Docker backend stack. The frontend dev server is
    stopped separately with Ctrl+C in its own terminal.

    Run:  powershell -ExecutionPolicy Bypass -File scripts\dev-down.ps1
          powershell -ExecutionPolicy Bypass -File scripts\dev-down.ps1 -Volumes   # also wipe data

.PARAMETER Volumes
    Also remove named volumes (postgres/redis/minio data). Destroys local data.
#>
param(
    [switch]$Volumes
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Get-Compose {
    try { docker compose version *> $null; if ($LASTEXITCODE -eq 0) { return ,@("docker","compose") } } catch {}
    try { docker-compose version *> $null; if ($LASTEXITCODE -eq 0) { return ,@("docker-compose") } } catch {}
    throw "Docker Compose not found."
}
$Compose      = Get-Compose
$ComposeExe   = $Compose[0]
$ComposeArgs  = @(); if ($Compose.Count -gt 1) { $ComposeArgs = $Compose[1..($Compose.Count - 1)] }
function Compose { & $ComposeExe @ComposeArgs @args }

if ($Volumes) {
    Write-Host "==> Stopping stack and REMOVING volumes (local data will be lost)..." -ForegroundColor Yellow
    Compose down -v
} else {
    Write-Host "==> Stopping stack (data volumes kept)..." -ForegroundColor Cyan
    Compose down
}
Write-Host "Done." -ForegroundColor Green
