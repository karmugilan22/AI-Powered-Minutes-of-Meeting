@echo off
echo Starting AI-Powered MoM Assistant Backend...
if not exist .venv (
    echo Error: Virtual environment .venv not found.
    echo Please run "python -m venv .venv" and "pip install -r requirements.txt" first.
    pause
    exit /b 1
)

:: Run FastAPI using the virtual environment's uvicorn
.venv\Scripts\uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
pause
