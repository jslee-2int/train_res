@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto fail
)
".venv\Scripts\python.exe" -m pip install --upgrade -r requirements.txt
if errorlevel 1 goto fail
echo Setup complete. Open start_app.bat to launch.
pause
exit /b 0
:fail
echo Setup failed. Please check Python and your internet connection.
pause
exit /b 1
