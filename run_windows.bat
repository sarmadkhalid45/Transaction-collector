@echo off
cd /d "%~dp0"
if not exist ".env" copy ".env.example" ".env"
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 goto :failed
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :failed
echo.
echo Starting LedgerBridge at http://127.0.0.1:8000
.venv\Scripts\python.exe app.py
goto :end
:failed
echo Setup failed. Install Python 3.11 or newer and retry.
pause
:end
