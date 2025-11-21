# RAG OS Unified Startup Script
# Starts FastAPI backend and Streamlit app together
# Usage: .\scripts\start_rag_os.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  RAG OS Startup Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Ollama is running (optional but recommended)
Write-Host "[1/4] Checking Ollama..." -ForegroundColor Yellow
try {
    $ollamaCheck = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 -ErrorAction Stop
    Write-Host "  ✓ Ollama is running" -ForegroundColor Green
} catch {
    Write-Host "  ⚠ Ollama not detected. Make sure Ollama is running: `ollama serve`" -ForegroundColor Yellow
    Write-Host "     Continuing anyway..." -ForegroundColor Gray
}
Write-Host ""

# Check for port conflicts
Write-Host "[2/4] Checking ports..." -ForegroundColor Yellow
try {
    $port8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
    $port8501 = Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue

    if ($port8000) {
        Write-Host "  ⚠ Port 8000 is already in use. Backend may already be running." -ForegroundColor Yellow
        $kill = Read-Host "  Kill existing process? (y/n)"
        if ($kill -eq "y" -or $kill -eq "Y") {
            $process = Get-Process -Id $port8000.OwningProcess -ErrorAction SilentlyContinue
            if ($process) {
                Stop-Process -Id $process.Id -Force
                Write-Host "  ✓ Killed process on port 8000" -ForegroundColor Green
                Start-Sleep -Seconds 1
            }
        }
    }

    if ($port8501) {
        Write-Host "  ⚠ Port 8501 is already in use. Streamlit may already be running." -ForegroundColor Yellow
        $kill = Read-Host "  Kill existing process? (y/n)"
        if ($kill -eq "y" -or $kill -eq "Y") {
            $process = Get-Process -Id $port8501.OwningProcess -ErrorAction SilentlyContinue
            if ($process) {
                Stop-Process -Id $process.Id -Force
                Write-Host "  ✓ Killed process on port 8501" -ForegroundColor Green
                Start-Sleep -Seconds 1
            }
        }
    }
} catch {
    # Get-NetTCPConnection might not be available, skip port check
    Write-Host "  ⚠ Could not check ports (skipping)" -ForegroundColor Yellow
}
Write-Host ""

# Initialize database
Write-Host "[3/4] Initializing database..." -ForegroundColor Yellow
try {
    python -m backend.models 2>&1 | Out-Null
    Write-Host "  ✓ Database initialized" -ForegroundColor Green
} catch {
    Write-Host "  ⚠ Database initialization warning (may already exist)" -ForegroundColor Yellow
}
Write-Host ""

# Start FastAPI backend
Write-Host "[4/4] Starting services..." -ForegroundColor Yellow
Write-Host "  → Starting FastAPI backend on http://127.0.0.1:8000" -ForegroundColor Cyan

# Get the project root directory (parent of scripts folder)
$projectRoot = (Get-Item $PSScriptRoot).Parent.FullName

# Start backend in new CMD window (cmd /k keeps window open even on error)
# Use the same approach as batch script for reliability
$backendCmd = "cd /d `"$projectRoot`" && python -m backend.app"

Start-Process cmd -ArgumentList "/k", $backendCmd -WindowStyle Normal

# Wait for backend to be ready
Write-Host "  → Waiting for backend to start..." -ForegroundColor Gray
$maxAttempts = 30
$attempt = 0
$backendReady = $false

while ($attempt -lt $maxAttempts -and -not $backendReady) {
    Start-Sleep -Seconds 1
    $attempt++
    try {
        $healthCheck = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -TimeoutSec 1 -ErrorAction Stop
        if ($healthCheck.StatusCode -eq 200) {
            $backendReady = $true
            Write-Host "  ✓ Backend is ready!" -ForegroundColor Green
        }
    } catch {
        # Still waiting...
        if ($attempt % 5 -eq 0) {
            Write-Host "    ...still waiting ($attempt/$maxAttempts)" -ForegroundColor Gray
        }
    }
}

if (-not $backendReady) {
    Write-Host "  ⚠ Backend did not respond in time, but continuing..." -ForegroundColor Yellow
}

# Start Streamlit
Write-Host "  → Starting Streamlit app on http://127.0.0.1:8501" -ForegroundColor Cyan

$streamlitCmd = "cd /d `"$projectRoot`" && streamlit run src/app/streamlit_app.py --server.port=8501 --server.address=127.0.0.1"

Start-Process cmd -ArgumentList "/k", $streamlitCmd -WindowStyle Normal

# Wait a moment for Streamlit to start
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Services Started!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Backend API:  http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  API Docs:     http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "  Streamlit UI: http://127.0.0.1:8501" -ForegroundColor White
Write-Host ""
Write-Host "  Press any key to open Streamlit in browser..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# Open browser
Start-Process "http://127.0.0.1:8501"

Write-Host ""
Write-Host "  ✓ Browser opened!" -ForegroundColor Green
Write-Host ""
Write-Host "  Note: Services are running in separate CMD windows." -ForegroundColor Gray
Write-Host "        You should see two new windows:" -ForegroundColor Gray
Write-Host "        - 'RAG OS Backend' (FastAPI)" -ForegroundColor Gray
Write-Host "        - 'RAG OS Streamlit' (Streamlit UI)" -ForegroundColor Gray
Write-Host "        Close those windows to stop the services." -ForegroundColor Gray
Write-Host ""
Write-Host "  If windows don't appear, check Task Manager for python.exe processes." -ForegroundColor Yellow
Write-Host ""

