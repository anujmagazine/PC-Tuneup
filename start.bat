@echo off
title PC TuneUp - Local System Optimizer
echo ============================================================
echo   PC TuneUp - Local System Optimizer
echo   Installing dependencies...
echo ============================================================

cd /d "%~dp0"

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    py --version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python is not installed.
        echo Please install Python from https://www.python.org/downloads/
        echo Make sure to check "Add Python to PATH" during installation.
        pause
        exit /b 1
    )
    set PYTHON=py
) else (
    set PYTHON=python
)

:: Install dependencies using python -m pip
%PYTHON% -m pip install -r requirements.txt --quiet

echo.
echo Starting PC TuneUp...
echo Your browser will open automatically.
echo Press Ctrl+C to stop the app.
echo ============================================================

%PYTHON% app.py
pause
