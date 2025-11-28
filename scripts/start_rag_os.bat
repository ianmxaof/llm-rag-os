@echo off
REM RAG OS Unified Startup Script (Batch Version)
REM Starts Ollama, FastAPI backend, and Streamlit app together
REM Usage: scripts\start_rag_os.bat

cd /d "%~dp0.."

echo ========================================
echo   POWERCORE RAG OS Startup Script
echo ========================================
echo.

REM Check if Python 3.13 venv exists
if not exist ".venv-313\Scripts\python.exe" (
    echo [ERROR] Python 3.13 virtual environment not found!
    echo.
    echo Please run the setup script first:
    echo   scripts\setup_python313.bat
    echo.
    echo Or create it manually:
    echo   python3.13 -m venv .venv-313
    echo   .venv-313\Scripts\activate
    echo   pip install -r requirements.txt
    echo   pip install feedparser langchain
    echo.
    pause
    exit /b 1
)

REM Auto-install missing dependencies
echo [1/5] Installing missing dependencies (one-time only)...
.venv-313\Scripts\pip.exe install --quiet feedparser langchain langchain-text-splitters sqlalchemy scikit-learn >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Dependencies checked
) else (
    echo   [WARN] Dependency check had issues, but continuing...
)
echo.

REM Check if Ollama is running, start if not
echo [2/5] Checking Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Ollama is already running
) else (
    echo   [INFO] Starting Ollama...
    set OLLAMA_PATH=C:\Users\%USERNAME%\AppData\Local\Programs\Ollama\ollama.exe
    if exist "%OLLAMA_PATH%" (
        start "" "%OLLAMA_PATH%" serve
        echo   [OK] Ollama started
        timeout /t 4 /nobreak >nul
    ) else (
        echo   [WARN] Ollama not found at default path. Please start manually: ollama serve
        echo          Continuing anyway...
    )
)
echo.

REM Verify critical dependencies
echo [3/5] Verifying critical dependencies...
.venv-313\Scripts\python.exe -c "import sqlalchemy; import chromadb; import sklearn; import langchain; print('OK')" >nul 2>&1
if %errorlevel% neq 0 (
    echo   [WARN] Missing critical dependencies, installing...
    .venv-313\Scripts\pip.exe install --quiet sqlalchemy chromadb scikit-learn langchain >nul 2>&1
)
echo   [OK] Dependencies verified
echo.

REM Initialize database
echo [4/6] Initializing database...
.venv-313\Scripts\python.exe -m backend.models >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Database initialized
) else (
    echo   [WARN] Database initialization warning (may already exist)
)
echo.

REM Start FastAPI backend
echo [5/6] Starting FastAPI backend...
echo   Starting on http://127.0.0.1:8000
start "Powercore Backend" cmd /k "cd /d %~dp0.. && .venv-313\Scripts\activate && uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000"

REM Wait for backend to start with retry logic
echo   Waiting for backend to start...
set BACKEND_READY=0
set MAX_ATTEMPTS=15
set ATTEMPT=0

:check_backend
timeout /t 2 /nobreak >nul
set /a ATTEMPT+=1
curl -s http://127.0.0.1:8000/health >nul 2>&1
if %errorlevel% equ 0 (
    set BACKEND_READY=1
    echo   [OK] Backend is ready!
    goto backend_ready
)
if %ATTEMPT% geq %MAX_ATTEMPTS% (
    echo   [WARN] Backend did not respond after %MAX_ATTEMPTS% attempts, but continuing...
    goto backend_ready
)
goto check_backend

:backend_ready
echo.

REM Start Streamlit
echo [6/6] Starting Streamlit app...
echo   Starting on http://127.0.0.1:8501
start "Powercore RAG" /MAX cmd /k "cd /d %~dp0.. && .venv-313\Scripts\activate && streamlit run src/app/streamlit_app.py --server.headless true --server.maxMessageSize=0 --server.port=8501 --server.address=127.0.0.1"

REM Wait for Streamlit to start
timeout /t 3 /nobreak >nul

echo.
echo ╔═══════════════════════════════════════════════════════════╗
echo ║           POWERCORE RAG IS NOW FULLY ALIVE                ║
echo ║   Ollama     → running                                    ║
echo ║   Backend    → http://127.0.0.1:8000                       ║
echo ║   Dashboard  → http://localhost:8501                      ║
echo ╚═══════════════════════════════════════════════════════════╝
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

