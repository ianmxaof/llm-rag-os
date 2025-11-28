# Python 3.13 Migration Guide

## Quick Start

1. **Install Python 3.13**
   - Download: https://www.python.org/ftp/python/3.13.0/python-3.13.0-amd64.exe
   - Run installer and check "Add Python to PATH"
   - Restart your terminal/command prompt

2. **Run Setup Script**
   ```batch
   scripts\setup_python313.bat
   ```
   This will:
   - Create `.venv-313` virtual environment
   - Install all dependencies
   - Verify backend imports correctly

3. **Start RAG OS**
   ```batch
   scripts\start_rag_os.bat
   ```

## What Changed

- **Launcher Script** (`scripts/start_rag_os.bat`): Now uses Python 3.13 venv
- **Setup Script** (`scripts/setup_python313.bat`): Automated venv creation and dependency installation
- **Virtual Environment**: `.venv-313` (isolated from Python 3.14)

## Manual Setup (Alternative)

If you prefer to set up manually:

```batch
# Create venv
python3.13 -m venv .venv-313

# Activate venv
.venv-313\Scripts\activate

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
pip install feedparser langchain uvicorn fastapi streamlit

# Test backend import
python -c "from backend.app import app; print('OK')"
```

## Troubleshooting

### Python 3.13 Not Found
- Ensure Python 3.13 is installed and added to PATH
- Try: `python3.13 --version` to verify
- Restart terminal after installation

### Backend Import Errors
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check that chromadb installs without errors
- Verify Python version: `python --version` should show 3.13.0

### Services Won't Start
- Check that `.venv-313\Scripts\python.exe` exists
- Verify venv is activated in service windows
- Check service windows for error messages

## Reverting to Python 3.14

If you need to switch back:
1. Edit `scripts/start_rag_os.bat`
2. Replace `.venv-313\Scripts\` paths with system Python
3. Or create a new venv with Python 3.14

## Notes

- Python 3.14 can remain installed (won't interfere)
- `.venv-313` is automatically ignored by git (added to `.gitignore`)
- All services now run in Python 3.13 environment
- Chromadb compatibility issues should be resolved

