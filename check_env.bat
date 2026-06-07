@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%" || goto FAIL
set "APP_ROOT=%CD%"
set "PY=%APP_ROOT%\.venv\Scripts\python.exe"

echo ==================================================
echo 쯔꾸르붕이 environment check
echo ==================================================
echo Project root: %APP_ROOT%
echo Expected PY : %PY%
echo.

if not exist "%PY%" (
    echo [ERROR] Root .venv Python not found. Run setup_venv.bat first.
    pause
    exit /b 1
)

"%PY%" -c "import sys, os; print('sys.executable =', sys.executable); print('version        =', sys.version); print('cwd            =', os.getcwd()); raise SystemExit(0 if sys.version_info[:2] == (3,11) else 1)"
if errorlevel 1 (
    echo [ERROR] Python version mismatch. Recreate .venv with setup_venv.bat.
    pause
    exit /b 1
)

echo.
echo Import check:
"%PY%" -c "import PyQt6, cv2, numpy, PIL, requests, openai, PyInstaller; print('core imports OK')"
if errorlevel 1 goto FAIL
"%PY%" -c "import replicate; print('replicate import OK')"
if errorlevel 1 echo [WARN] replicate import failed. API translation can still run, but setup_venv.bat should refresh app requirements.

echo.
echo [OK] Root .venv looks usable for source run and build.
pause
exit /b 0

:FAIL
echo.
echo [ERROR] Environment check failed.
pause
exit /b 1
