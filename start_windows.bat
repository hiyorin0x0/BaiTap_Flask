@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==========================================
echo        SOA FLASK DEMO - START
 echo ==========================================
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating Python virtual environment...
    py -3 -m venv .venv
    if errorlevel 1 (
        echo Cannot use py launcher. Trying python...
        python -m venv .venv
    )
)
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Python 3 or venv is missing.
    pause
    exit /b 1
)
echo [2/3] Installing libraries (Flask, requests, PyJWT)...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Cannot install Flask/requests. Check internet and Python.
    pause
    exit /b 1
)
echo [3/3] Starting APIs and web client...
echo Open browser at http://127.0.0.1:5000
".venv\Scripts\python.exe" run_all.py
pause
