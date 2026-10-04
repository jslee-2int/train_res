@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing_python
".venv\Scripts\python.exe" -m pip install -r requirements.txt "pyinstaller==6.22.3"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" build_icon.py
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name KTXSeatWatch --icon "%~dp0build\KTXSeatWatch.ico" --specpath build ktx_app.py
if errorlevel 1 goto failed
echo.
".venv\Scripts\python.exe" -c "import ctypes; from pathlib import Path; notify = ctypes.windll.shell32.SHChangeNotify; notify.argtypes = [ctypes.c_long, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_void_p]; notify(0x2000, 0x1005, str(Path('dist/KTXSeatWatch.exe').resolve()), None)"
echo Build complete: %~dp0dist\KTXSeatWatch.exe
exit /b 0
:missing_python
echo Virtual environment not found. Run setup_app.bat first.
pause
exit /b 1
:failed
echo Build failed. See the output above.
pause
exit /b 1
