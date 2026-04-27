@echo off
cd /d "%~dp0"

:: ---------------------------------------------------------------
:: STAGE 1 (runs as normal user): find the real Python path,
:: then re-launch this script as admin with that path as argument
:: ---------------------------------------------------------------
if "%~1"=="" (

    :: Find Python executable path before elevating
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

    echo Found Python at: %PYPATH%
    echo Launching with admin privileges...

    :: Re-launch this bat as admin, passing the python path as argument
    powershell -Command "Start-Process -FilePath '%~f0' -ArgumentList '\"%PYPATH%\"' -Verb RunAs"
    exit /b
)

:: ---------------------------------------------------------------
:: STAGE 2 (runs as admin): %1 is the Python path passed from Stage 1
:: ---------------------------------------------------------------
title PC TuneUp - Admin Mode

echo ============================================================
echo   PC TuneUp - Local System Optimizer (ADMIN MODE)
echo ============================================================
echo.
echo Using Python: %~1
echo.

"%~1" --version
if errorlevel 1 (
    echo.
    echo ERROR: Could not run Python at: %~1
    echo.
    echo Try this instead - open an Admin Command Prompt and run:
    echo   py app.py
    echo from this folder.
    pause
    exit /b 1
)

echo Installing dependencies...
"%~1" -m pip install -r requirements.txt --quiet

echo.
echo Starting PC TuneUp...
echo Your browser will open at http://localhost:5555
echo Press Ctrl+C to stop.
echo ============================================================
echo.
"%~1" app.py
pause
