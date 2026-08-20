@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Auto Live2D - launcher
echo ============================================

echo [setup] Installing dependencies (first run may take a while)...
python -m pip install --upgrade pip
if errorlevel 1 goto :err
python -m pip install -r requirements.txt
if errorlevel 1 goto :err

echo.
echo [run] Starting Auto Live2D...
python main.py
goto :eof

:err
echo.
echo [error] Setup failed. Make sure Python 3.10+ is installed and on PATH.
echo         (run "python --version" to check)
pause
