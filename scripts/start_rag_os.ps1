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
Write-Host "  → Starting FastAPI backend (quiet)…" -ForegroundColor Cyan

# Get the project root directory (parent of scripts folder)
$projectRoot = (Get-Item $PSScriptRoot).Parent.FullName

# Quiet start: minimized consoles (do not steal focus while typing).
# Logs: data/logs/backend.log and data/logs/streamlit.log
$logDir = Join-Path $projectRoot "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$backendLog = Join-Path $logDir "backend.log"
$streamlitLog = Join-Path $logDir "streamlit.log"

# Prefer 8000; if busy use 8010 and set RAG_API_BASE for Streamlit
$ragPort = 8000
try {
    $busy = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
    if ($busy) { $ragPort = 8010 }
} catch { }
$env:RAG_API_BASE = "http://127.0.0.1:$ragPort"
Write-Host "  → RAG API port: $ragPort (RAG_API_BASE=$env:RAG_API_BASE)" -ForegroundColor Cyan

$backendCmd = "cd /d `"$projectRoot`" && set RAG_API_BASE=$env:RAG_API_BASE&& .venv-313\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port $ragPort >> `"$backendLog`" 2>&1"

Start-Process cmd -ArgumentList "/c", $backendCmd -WindowStyle Minimized

# Wait for backend to be ready
Write-Host "  → Waiting for backend to start..." -ForegroundColor Gray
$maxAttempts = 30
$attempt = 0
$backendReady = $false

while ($attempt -lt $maxAttempts -and -not $backendReady) {
    Start-Sleep -Seconds 1
    $attempt++
    try {
        $healthCheck = Invoke-WebRequest -Uri "http://127.0.0.1:$ragPort/health" -TimeoutSec 1 -ErrorAction Stop
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

# Quiet notes watcher on by default — new vault captures hit Lance without a scavenger hunt
Write-Host "  → Starting notes watcher (quiet, via API)..." -ForegroundColor Cyan
try {
    $watchUrl = "$($env:RAG_API_BASE)/ingest/watch/notes/start"
    $watchResp = Invoke-WebRequest -Uri $watchUrl -Method POST -TimeoutSec 8 -ErrorAction Stop
    Write-Host "  ✓ Notes watcher started (new .md → Lance)" -ForegroundColor Green
} catch {
    Write-Host "  ⚠ Notes watcher API start failed: $_" -ForegroundColor Yellow
    Write-Host "     Ops home → Start watcher, or Settings → Obsidian Sync" -ForegroundColor Gray
}

# Start Streamlit (minimized — Ops home is the landing page)
Write-Host "  → Starting Streamlit app on http://127.0.0.1:8501 (minimized)" -ForegroundColor Cyan

$streamlitCmd = "cd /d `"$projectRoot`" && set RAG_API_BASE=$env:RAG_API_BASE&& .venv-313\Scripts\python.exe -m streamlit run src/app/streamlit_app.py --server.headless true --server.port=8501 --server.address=127.0.0.1 >> `"$streamlitLog`" 2>&1"

Start-Process cmd -ArgumentList "/c", $streamlitCmd -WindowStyle Minimized

# Wait a moment for Streamlit to start
Start-Sleep -Seconds 4

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Services Started (quiet)!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Backend API:  http://127.0.0.1:$ragPort" -ForegroundColor White
Write-Host "  API Docs:     http://127.0.0.1:$ragPort/docs" -ForegroundColor White
Write-Host "  Streamlit UI: http://127.0.0.1:8501  (Ops home)" -ForegroundColor White
Write-Host "  Notes watch:  on by default (new .md → Lance)" -ForegroundColor White
Write-Host "  Logs:         $logDir" -ForegroundColor Gray
Write-Host ""
Write-Host "  Consoles are minimized on purpose so they do not steal focus." -ForegroundColor Gray
Write-Host "  Stop services from Task Manager (python/streamlit) or close minimized cmds." -ForegroundColor Gray
Write-Host ""

Start-Process "http://127.0.0.1:8501"
Write-Host "  ✓ Browser opened at Ops home." -ForegroundColor Green
Write-Host ""

