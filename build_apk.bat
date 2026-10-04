@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto failed
".venv\Scripts\python.exe" prepare_mobile.py
if errorlevel 1 goto failed
pushd mobile
call flutter build apk --release --target-platform android-arm64,android-x64
set "build_result=%ERRORLEVEL%"
popd
if not "%build_result%"=="0" goto failed
if not exist dist mkdir dist
copy /y "mobile\build\app\outputs\flutter-apk\app-release.apk" "dist\KTXSeatWatch.apk" >nul
if errorlevel 1 goto failed
echo APK ready: %~dp0dist\KTXSeatWatch.apk
exit /b 0
:failed
echo APK build failed. Check Flutter, Android SDK and the Python virtual environment.
exit /b 1
