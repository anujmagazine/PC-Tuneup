@echo off
cd /d "%~dp0"

:: ---------------------------------------------------------------
:: STAGE 1 (runs as normal user): relaunch this script elevated.
:: Detecting elevation via "net session" (rather than passing an
:: argument through Start-Process -Verb RunAs) avoids a real bug:
:: PowerShell single-quoted strings don't process backslash escapes,
:: so an argument like '\"C:\Program Files\...\python.exe\"' comes
:: through as a literal broken string with stray backslashes, and
:: Start-Process silently fails to launch the elevated instance.
:: ---------------------------------------------------------------
net session >nul 2>&1
if %errorlevel% == 0 goto :elevated

echo Requesting administrator access - click "Yes" on the prompt...
powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
exit /b

:elevated
title PC TuneUp - Admin Mode

echo ============================================================
echo   PC TuneUp - Local System Optimizer (ADMIN MODE)
echo ============================================================
echo.

:: Find Python executable path now that we're elevated
set PYPATH=
for /f "delims=" %%P in ('powershell -NoProfile -Command "(Get-Command python3,python,py -ErrorAction SilentlyContinue | Where-Object { $_.Source -notlike '*WindowsApps*' } | Select-Object -First 1).Source"') do set PYPATH=%%P

:: If not found outside WindowsApps, try WindowsApps as fallback
if not defined PYPATH (
    for /f "delims=" %%P in ('powershell -NoProfile -Command "(Get-Command python3,python,py -ErrorAction SilentlyContinue | Select-Object -First 1).Source"') do set PYPATH=%%P
)

if not defined PYPATH (
    echo ERROR: Python not found on this PC.
    echo.
    echo Please install Python from: https://www.python.org/downloads/
    echo During installation tick "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

echo Using Python: %PYPATH%
echo.

"%PYPATH%" --version
if errorlevel 1 (
    echo.
    echo ERROR: Could not run Python at: %PYPATH%
    echo.
    echo Try this instead - open an Admin Command Prompt and run:
    echo   py app.py
    echo from this folder.
    pause
    exit /b 1
)

echo Installing dependencies...
"%PYPATH%" -m pip install -r requirements.txt --quiet

echo.
echo Starting PC TuneUp...
echo Your browser will open at http://localhost:5555
echo Press Ctrl+C to stop.
echo ============================================================
echo.
"%PYPATH%" app.py
pause
