@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul

echo ==========================================
echo  YSB Game Editor - Maker Font Runtime Setup
echo ==========================================
echo.
echo This installs the dependencies required to convert RPG Maker MZ WOFF/WOFF2 fonts into Qt-loadable TTF caches.
echo Required packages: fonttools, brotli
echo.

set "VENV_DIR=%CD%\.venv"
set "PY=%VENV_DIR%\Scripts\python.exe"

if not exist "%PY%" (
    echo .venv was not found. Creating shared virtual environment...
    py -3.11 -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create .venv with Python 3.11.
        echo Install Python 3.11 or run setup_venv.bat first.
        pause
        exit /b 1
    )
)

echo Python:
"%PY%" --version
if errorlevel 1 goto FAIL

echo.
echo Installing font runtime dependencies...
"%PY%" -m pip install --upgrade pip
if errorlevel 1 goto FAIL
"%PY%" -m pip install fonttools brotli
if errorlevel 1 goto FAIL

echo.
echo Verifying imports...
"%PY%" -c "import fontTools, brotli; print('fontTools OK / brotli OK')"
if errorlevel 1 goto FAIL

echo.
echo Done. Reopen the project or run Options ^> Maker Display Environment Refresh.
echo.
pause
exit /b 0

:FAIL
echo.
echo [ERROR] Failed to install Maker font runtime dependencies.
echo Send a screenshot of this window.
pause
exit /b 1
