# PowerShell check script for Windows environments
$ErrorActionPreference = "Stop"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Bright Smile Dental Voice Assistant Check" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$ROOT_DIR = (Resolve-Path "$PSScriptRoot\..").Path

Write-Host "1. Checking required documentation..."
foreach ($doc in @("README.md", "DESIGN.md", "AI_USAGE.md")) {
    if (-not (Test-Path "$ROOT_DIR\$doc")) {
        Write-Error "Missing $doc"
        exit 1
    }
}
$aiUsageItems = Get-ChildItem "$ROOT_DIR\docs\ai-usage" -ErrorAction SilentlyContinue
if (-not $aiUsageItems -or $aiUsageItems.Count -eq 0) {
    Write-Error "docs/ai-usage/ must not be empty"
    exit 1
}
Write-Host "✓ Documentation checks passed" -ForegroundColor Green

Write-Host "2. Checking for committed secrets..."
$secretMatches = Get-ChildItem -Path $ROOT_DIR -Recurse -File `
    -Exclude "*.git*", "*node_modules*", "*.next*", "*__pycache__*" |
    Select-String -Pattern 'AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z-_]{35}|sk-[a-zA-Z0-9]{32,}|ghp_[a-zA-Z0-9]{36}'
if ($secretMatches) {
    Write-Error "Potential secrets found!"
    exit 1
}
Write-Host "✓ Secrets check passed" -ForegroundColor Green

Write-Host "3. Running backend tests..."
$env:PYTHONPATH = "$ROOT_DIR\backend\src"
python -m pytest "$ROOT_DIR\backend\tests"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Backend tests failed!"
    exit 1
}
Write-Host "✓ Backend tests passed" -ForegroundColor Green

Write-Host "4. Running frontend tests..."
Push-Location "$ROOT_DIR\frontend"
try {
    npm run test
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Frontend tests failed!"
        exit 1
    }
} finally {
    Pop-Location
}
Write-Host "✓ Frontend tests passed" -ForegroundColor Green

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "ALL GATES PASSED!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Cyan
