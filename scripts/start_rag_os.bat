@echo off
REM RAG OS Unified Startup Script (Batch Version)
REM Starts FastAPI backend and Streamlit app together
REM Usage: scripts\start_rag_os.bat

echo ========================================
echo   RAG OS Startup Script
echo ========================================
echo.

REM Check if Ollama is running (optional)
echo [1/4] Checking Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Ollama is running
) else (
    echo   [WARN] Ollama not detected. Make sure Ollama is running: ollama serve
    echo          Continuing anyway...
)
echo.

REM Initialize database
echo [2/4] Initializing database...
python -m backend.models >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Database initialized
) else (
    echo   [WARN] Database initialization warning (may already exist)
)
echo.

REM Start FastAPI backend
echo [3/4] Starting FastAPI backend...
echo   Starting on http://127.0.0.1:8000
start "RAG OS Backend" cmd /k "cd /d %~dp0.. && python -m backend.app"

REM Wait for backend to start
echo   Waiting for backend to start...
timeout /t 5 /nobreak >nul

REM Check if backend is ready (simple check)
curl -s http://127.0.0.1:8000/health >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Backend is ready!
) else (
    echo   [WARN] Backend may not be ready yet, but continuing...
)
echo.

REM Start Streamlit
echo [4/4] Starting Streamlit app...
echo   Starting on http://127.0.0.1:8501
start "RAG OS Streamlit" cmd /k "cd /d %~dp0.. && streamlit run src/app/streamlit_app.py --server.port=8501 --server.address=127.0.0.1"

REM Wait for Streamlit to start
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   Services Started!
echo ========================================
echo.
echo   Backend API:  http://127.0.0.1:8000
echo   API Docs:     http://127.0.0.1:8000/docs
echo   Streamlit UI: http://127.0.0.1:8501
echo.
echo   Opening Streamlit in browser...
start http://127.0.0.1:8501

echo.
echo   [OK] Browser opened!
echo.
echo   Note: Services are running in separate windows.
echo         Close those windows to stop the services.
echo.
pause

