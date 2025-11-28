# Cursor IDE Launch Commands for Powercore RAG

Quick reference for launching Powercore RAG from Cursor IDE terminal.

## Prerequisites

- Virtual environment `.venv-313` is activated (or use full path to Python)
- All dependencies installed
- Python 3.13.0

## Option 1: Using VS Code Tasks (Recommended)

### Start Backend Only
1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Type "Tasks: Run Task"
3. Select `start-backend`

### Start Streamlit Only  
1. Press `Ctrl+Shift+P`
2. Type "Tasks: Run Task"
3. Select `start-streamlit` (will wait for backend if not running)

### Start Both (Sequential)
1. Press `Ctrl+Shift+P`
2. Type "Tasks: Run Task"
3. Select `start-powercore`

## Option 2: Using Launch Configuration (One-Click)

1. Press `F5` or go to Run and Debug (`Ctrl+Shift+D`)
2. Select "Start Powercore RAG" from dropdown
3. Click the green play button

Or use the compound configuration:
- Select "Powercore RAG (Backend + Streamlit)" for both services

## Option 3: Manual Terminal Commands

### Single Terminal (Backend in Background)

**PowerShell:**
```powershell
# Start backend in background job
Start-Job -ScriptBlock { 
    Set-Location $using:PWD
    uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000 
}

# Wait 2 seconds for backend to start
Start-Sleep -Seconds 2

# Start Streamlit (foreground)
streamlit run src/app/streamlit_app.py --server.headless true --server.maxMessageSize=0 --server.port=8501 --server.address=127.0.0.1
```

**CMD:**
```cmd
start /B uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
timeout /t 2 /nobreak >nul
streamlit run src/app/streamlit_app.py --server.headless true --server.maxMessageSize=0 --server.port=8501 --server.address=127.0.0.1
```

### Two Separate Terminals

**Terminal 1 (Backend):**
```powershell
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 (Streamlit):**
```powershell
streamlit run src/app/streamlit_app.py --server.headless true --server.maxMessageSize=0 --server.port=8501 --server.address=127.0.0.1
```

## URLs

- **Backend API**: http://127.0.0.1:8000
- **API Docs**: http://127.0.0.1:8000/docs
- **Streamlit Dashboard**: http://127.0.0.1:8501

## Stopping Services

- **Tasks**: Press `Ctrl+C` in the terminal where the task is running
- **Launch Config**: Click the stop button in the debug toolbar
- **Manual**: Press `Ctrl+C` in each terminal

## Troubleshooting

### Backend won't start
- Check if port 8000 is already in use: `netstat -ano | findstr :8000`
- Ensure Python 3.13 is active (not 3.14): `python --version`
- Verify chromadb compatibility: `python -c "import chromadb; print('OK')"`

### Streamlit won't start
- Check if port 8501 is already in use: `netstat -ano | findstr :8501`
- Ensure backend is running first: `curl http://127.0.0.1:8000/health`

### Virtual Environment Not Activated
If `.venv-313` is not activated, use full path:
```powershell
.venv-313\Scripts\python.exe -m uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
.venv-313\Scripts\streamlit.exe run src/app/streamlit_app.py --server.headless true --server.maxMessageSize=0 --server.port=8501 --server.address=127.0.0.1
```

