@echo off
REM Initialize database
python -m backend.models

REM Start FastAPI backend
echo Starting FastAPI backend on http://127.0.0.1:8000
start "" uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000

timeout /t 2

echo Backend started. Open http://127.0.0.1:8000/docs for API documentation
pause

