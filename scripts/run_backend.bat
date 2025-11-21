@echo off
REM Backend-only startup script
REM For full RAG OS startup (Backend + Streamlit), use: scripts\start_rag_os.bat

REM Initialize database
python -m backend.models

REM Start FastAPI backend
echo Starting FastAPI backend on http://127.0.0.1:8000
start "" uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000

timeout /t 2

echo Backend started. Open http://127.0.0.1:8000/docs for API documentation
echo.
echo Note: This script only starts the backend.
echo       To start both backend and Streamlit, use: scripts\start_rag_os.bat
pause

