@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion

REM ==========================================================
REM  쯔꾸르붕이 Build
REM  - setup_venv.bat이 만든 프로젝트 루트 .venv만 사용한다.
REM  - py -3.11 / 시스템 Python으로 우회하지 않는다.
REM ==========================================================

set "BUILD_TOOLS_DIR=%~dp0"
for %%I in ("%BUILD_TOOLS_DIR%..") do set "PROJECT_ROOT=%%~fI"
cd /d "%PROJECT_ROOT%" || goto BOOT_FAIL

set "VENV_DIR=%PROJECT_ROOT%\.venv"
set "PY=%VENV_DIR%\Scripts\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%PROJECT_ROOT%;%PYTHONPATH%"
set "YSB_TOOL_EDITION=game"
set "YSB_REQUIRED_PYTHON=3.11"

title 쯔꾸르붕이 Build ^(root .venv / Python 3.11 only^)

echo 쯔꾸르붕이 build bootstrap
echo Project root: %PROJECT_ROOT%
echo Venv path   : %VENV_DIR%
echo Required    : Python 3.11.x
echo.

if not exist "%PY%" (
    echo [ERROR] Root .venv was not found.
    echo Run setup_venv.bat first. Build no longer creates a separate venv.
    goto END_FAIL
)

"%PY%" -c "import sys; print('sys.executable =', sys.executable); print('version        =', sys.version); raise SystemExit(0 if sys.version_info[:2] == (3,11) else 1)"
if errorlevel 1 (
    echo.
    echo [ERROR] Root .venv is not Python 3.11.x.
    echo Recreate it with setup_venv.bat.
    goto END_FAIL
)

"%PY%" "%BUILD_TOOLS_DIR%build_edition_bootstrap.py" game
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" (
    echo Build failed. Exit code: %RC%
    echo A bootstrap log should be in the project root: build_bootstrap_game_v*.log
    goto END_FAIL_CODE
)

echo Build completed.
goto END_OK

:BOOT_FAIL
echo Failed to enter project root: %PROJECT_ROOT%
goto END_FAIL

:END_FAIL
set "RC=1"

:END_FAIL_CODE
echo.
echo This window will stay open so the error can be checked.
pause
exit /b %RC%

:END_OK
echo.
pause
exit /b 0
