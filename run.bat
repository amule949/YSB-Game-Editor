@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion

REM ==========================================================
REM  쯔꾸르붕이 - Source Run
REM  - 반드시 프로젝트 루트의 .venv\Scripts\python.exe로 main.py를 실행한다.
REM  - 다른 Python, build_tools 내부 venv, 현재 CMD 작업 폴더를 사용하지 않는다.
REM ==========================================================

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%" || goto FAIL_ROOT

set "APP_ROOT=%CD%"
if not exist "main.py" (
    echo [ERROR] main.py not found. run.bat must be in the project root.
    pause
    exit /b 1
)
if not exist "ysb\__init__.py" (
    echo [ERROR] ysb package not found. run.bat must be in the project root.
    pause
    exit /b 1
)

set "VENV_DIR=%APP_ROOT%\.venv"
set "PY=%VENV_DIR%\Scripts\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%APP_ROOT%;%PYTHONPATH%"
set "YSB_TOOL_EDITION=game"

echo 쯔꾸르붕이 source run
echo Project root: %APP_ROOT%
echo Venv path   : %VENV_DIR%
echo Required    : Python 3.11.x
echo.

if not exist "%PY%" (
    echo [ERROR] Root .venv was not found.
    echo Run setup_venv.bat first.
    pause
    exit /b 1
)

"%PY%" -c "import sys; print('sys.executable =', sys.executable); print('version        =', sys.version); raise SystemExit(0 if sys.version_info[:2] == (3,11) else 1)"
if errorlevel 1 (
    echo.
    echo [ERROR] This root .venv is not Python 3.11.x.
    echo Recreate it with setup_venv.bat.
    pause
    exit /b 1
)

echo.
echo Starting 쯔꾸르붕이...
"%PY%" "%APP_ROOT%\main.py" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo.
    echo [ERROR] Program exited with code %RC%.
    echo Check logs under %%LOCALAPPDATA%%\YSBGameEditor\logs if a startup crash log was written.
    pause
)
exit /b %RC%

:FAIL_ROOT
echo [ERROR] Failed to enter script directory.
pause
exit /b 1
