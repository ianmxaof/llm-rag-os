# Intelligence OS Setup Script (Path A - Minimal)
# Creates minimal Docker setup for immediate intelligence feed

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Intelligence OS - Minimal Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$projectRoot = (Get-Item $PSScriptRoot).Parent.FullName
$intelDir = Join-Path $projectRoot "intelligence-data"

# Create directories
Write-Host "[1/4] Creating directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "$intelDir\n8n" | Out-Null
New-Item -ItemType Directory -Force -Path "$intelDir\out" | Out-Null
Write-Host "  ✓ Directories created" -ForegroundColor Green
Write-Host ""

# Check for .env.intelligence
Write-Host "[2/4] Checking configuration..." -ForegroundColor Yellow
$envFile = Join-Path $projectRoot ".env.intelligence"
if (-not (Test-Path $envFile)) {
    Write-Host "  ⚠ .env.intelligence not found" -ForegroundColor Yellow
    Write-Host "  → Creating from template..." -ForegroundColor Gray
    Copy-Item "$projectRoot\.env.intelligence.example" $envFile
    Write-Host "  ✓ Template created at: $envFile" -ForegroundColor Green
    Write-Host "  → Please edit .env.intelligence and add your API keys" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "  ✓ Configuration file found" -ForegroundColor Green
    Write-Host ""
}

# Check Docker
Write-Host "[3/4] Checking Docker..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version 2>&1
    Write-Host "  ✓ Docker is available: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Docker not found. Please install Docker Desktop" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Instructions
Write-Host "[4/4] Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Edit .env.intelligence and add your API keys" -ForegroundColor White
Write-Host "  2. Start services: docker compose -f docker/intelligence-minimal.yml up -d" -ForegroundColor White
Write-Host "  3. Open N8N: http://localhost:5678 (admin / changeme)" -ForegroundColor White
Write-Host "  4. Import the workflow JSON (provided separately)" -ForegroundColor White
Write-Host "  5. Link output folder:" -ForegroundColor White
Write-Host "     New-Item -ItemType SymbolicLink -Path `"knowledge/inbox/intelligence-feed`" -Target `"$intelDir\out`"" -ForegroundColor Gray
Write-Host ""
Write-Host "To pause: docker compose -f docker/intelligence-minimal.yml pause" -ForegroundColor Yellow
Write-Host "To stop:  docker compose -f docker/intelligence-minimal.yml stop" -ForegroundColor Yellow
Write-Host ""

