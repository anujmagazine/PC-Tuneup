@echo off
REM Builds PCTuneUp.exe - a single-file, no-install-needed executable.
REM Run this on your dev PC. Copy dist\PCTuneUp.exe to any Windows PC.

cd /d "%~dp0"

echo Installing build dependencies...
python -m pip install -q pyinstaller flask psutil wmi pywin32

echo Building PCTuneUp.exe ...
python -m PyInstaller --onefile --name PCTuneUp ^
  --add-data "templates;templates" ^
  --hidden-import win32timezone ^
  --noconfirm --clean ^
  app.py

if exist dist\PCTuneUp.exe (
  echo.
  echo SUCCESS: dist\PCTuneUp.exe is ready.
  echo Copy that one file to any Windows PC and double-click it.
) else (
  echo BUILD FAILED - see output above.
)
pause
