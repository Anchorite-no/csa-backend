$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $repoRoot

if (-not (Test-Path (Join-Path $repoRoot '.githooks'))) {
    throw 'Missing .githooks directory.'
}

& git config core.hooksPath .githooks
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to set core.hooksPath.'
}

Write-Host 'Installed git hooks for backend.'
Write-Host 'core.hooksPath=.githooks'
