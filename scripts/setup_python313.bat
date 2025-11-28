@echo off
REM Python 3.13 Virtual Environment Setup Script
REM Creates and configures the .venv-313 virtual environment
REM Usage: scripts\setup_python313.bat

cd /d "%~dp0.."

echo ========================================
echo   Python 3.13 Virtual Environment Setup
echo ========================================
echo.

REM Check if Python 3.13 is available
echo [1/6] Checking for Python 3.13...
python3.13 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   [ERROR] Python 3.13 not found!
    echo.
    echo   Please install Python 3.13.0 first:
    echo   1. Download from: https://www.python.org/ftp/python/3.13.0/python-3.13.0-amd64.exe
    echo   2. Run installer and check "Add Python to PATH"
    echo   3. Restart this script
    echo.
    pause
    exit /b 1
)

python3.13 --version
echo   [OK] Python 3.13 found
echo.

REM Check if venv already exists
if exist ".venv-313\Scripts\python.exe" (
    echo [2/6] Virtual environment already exists
    echo   [INFO] Skipping venv creation
    echo.
    goto :activate
)

REM Create virtual environment
echo [2/6] Creating virtual environment...
python3.13 -m venv .venv-313
if %errorlevel% neq 0 (
    echo   [ERROR] Failed to create virtual environment
    pause
    exit /b 1
)
echo   [OK] Virtual environment created
echo.

:activate
REM Activate and upgrade pip
echo [3/6] Activating virtual environment and upgrading pip...
call .venv-313\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo   [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)

python -m pip install --upgrade pip >nul 2>&1
if %errorlevel% neq 0 (
    echo   [WARN] Failed to upgrade pip, but continuing...
) else (
    echo   [OK] Pip upgraded
)
echo.

REM Verify Python version
echo [4/6] Verifying Python version...
python --version
for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo   Python version: %PYTHON_VERSION%
if not "%PYTHON_VERSION%"=="3.13.0" (
    echo   [WARN] Expected Python 3.13.0, but got %PYTHON_VERSION%
    echo          This may cause compatibility issues
)
echo.

REM Install dependencies from requirements.txt
echo [5/6] Installing dependencies from requirements.txt...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo   [ERROR] Failed to install dependencies from requirements.txt
    pause
    exit /b 1
)
echo   [OK] Requirements installed
echo.

REM Install additional dependencies
echo [6/7] Installing additional dependencies...
pip install feedparser langchain uvicorn fastapi streamlit
if %errorlevel% neq 0 (
    echo   [WARN] Some additional dependencies may have failed to install
) else (
    echo   [OK] Additional dependencies installed
)
echo.

REM Explicitly install critical dependencies that sometimes get skipped
echo [7/7] Verifying critical dependencies (sqlalchemy, chromadb, sklearn, etc.)...
pip install sqlalchemy chromadb langchain langchain-community langchain-text-splitters scikit-learn tiktoken sentence-transformers psutil
if %errorlevel% neq 0 (
    echo   [WARN] Some critical dependencies may have failed to install
) else (
    echo   [OK] Critical dependencies verified
)
echo.

REM Test critical imports before backend
echo [TEST] Testing critical imports...
python -c "import sqlalchemy; import chromadb; import sklearn; import langchain; print('   [OK] Critical imports successful')" 2>&1
if %errorlevel% neq 0 (
    echo   [WARN] Some critical imports failed, installing missing packages...
    pip install sqlalchemy chromadb scikit-learn langchain >nul 2>&1
)
echo.

REM Test backend import
echo [TEST] Testing backend import...
python -c "from backend.app import app; print('   [OK] Backend imports successfully')" 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Backend import test passed!
) else (
    echo   [WARN] Backend import test failed - check errors above
    echo          Common issues: missing sklearn, langchain, or chromadb compatibility
    echo          Try: pip install scikit-learn langchain chromadb
)
echo.

echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo   Virtual environment: .venv-313
echo   Python version: %PYTHON_VERSION%
echo.
echo   Next steps:
echo   1. Run: scripts\start_rag_os.bat
echo   2. All services should start without chromadb errors
echo.
pause

