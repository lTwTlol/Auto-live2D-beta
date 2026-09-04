@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "VENV_DIR=%CD%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_ACTIVATE=%VENV_DIR%\Scripts\activate.bat"
set "VENV_WAS_CREATED=0"

echo ============================================
echo  Auto Live2D - launcher
echo ============================================

if exist "%VENV_PYTHON%" goto :activate_venv

echo [setup] Virtual environment not found. Creating .venv...
set "BOOTSTRAP_PYTHON="

where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if not errorlevel 1 set "BOOTSTRAP_PYTHON=py -3"
)

if not defined BOOTSTRAP_PYTHON (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
        if not errorlevel 1 set "BOOTSTRAP_PYTHON=python"
    )
)

if not defined BOOTSTRAP_PYTHON goto :python_not_found

%BOOTSTRAP_PYTHON% --version
%BOOTSTRAP_PYTHON% -m venv "%VENV_DIR%"
if errorlevel 1 goto :venv_create_failed
set "VENV_WAS_CREATED=1"

:activate_venv
if not exist "%VENV_ACTIVATE%" goto :venv_invalid

call "%VENV_ACTIVATE%"
if errorlevel 1 goto :venv_invalid

"%VENV_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto :venv_invalid

if "%VENV_WAS_CREATED%"=="1" (
    echo [setup] Updating pip in .venv...
    "%VENV_PYTHON%" -m pip install --upgrade pip
    if errorlevel 1 goto :dependency_failed
)

echo [setup] Installing dependencies into .venv...
"%VENV_PYTHON%" -m pip install --disable-pip-version-check -r "%~dp0requirements.txt"
if errorlevel 1 goto :dependency_failed

echo.
echo [run] Starting Auto Live2D with .venv...
"%VENV_PYTHON%" "%~dp0main.py"
set "APP_EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %APP_EXIT_CODE%

:python_not_found
echo.
echo [error] Python 3.10 or later is required to create .venv.
echo         Install Python and make either "py" or "python" available on PATH.
goto :failed

:venv_create_failed
echo.
echo [error] Failed to create "%VENV_DIR%".
echo         Make sure the Python venv module is available.
goto :failed

:venv_invalid
echo.
echo [error] The existing .venv is incomplete, broken, or uses Python older than 3.10.
echo         Remove "%VENV_DIR%" and run this launcher again to recreate it.
goto :failed

:dependency_failed
echo.
echo [error] Failed to install dependencies into "%VENV_DIR%".
goto :failed

:failed
pause
endlocal
exit /b 1
