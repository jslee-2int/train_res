@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" goto missing_python
if not exist "%~dp0logs" mkdir "%~dp0logs"
set "launch_log=%~dp0logs\launch_%RANDOM%_%RANDOM%.log"
echo Starting KTX Seat Watch...
echo Python: %~dp0.venv\Scripts\python.exe
echo Log: %launch_log%
echo Launch: %DATE% %TIME% > "%launch_log%"
if errorlevel 1 goto log_failed
"%~dp0.venv\Scripts\python.exe" -u -X utf8 -X faulthandler "%~dp0ktx_app.py" %* >> "%launch_log%" 2>&1
set "app_exit=%ERRORLEVEL%"
echo Exit code: %app_exit% >> "%launch_log%"
if not "%app_exit%"=="0" goto launch_failed
exit /b 0
:missing_python
echo Virtual environment not found. Run setup_app.bat first.
pause
exit /b 1
:launch_failed
echo.
echo Application exited with error code %app_exit%.
type "%launch_log%"
echo.
echo Full log: %launch_log%
pause
exit /b %app_exit%
:log_failed
echo Cannot create a log file in %~dp0logs
pause
exit /b 1
