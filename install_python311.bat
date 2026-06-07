@echo off
setlocal

title YSB Tool - Install Python 3.11

echo ============================================================
echo YSB Tool - Install Python 3.11
echo ============================================================
echo.
echo This script installs Python 3.11 for the current Windows user.
echo Existing Python 3.12/3.13 installations will NOT be removed.
echo.

py -3.11 --version >nul 2>&1
if not errorlevel 1 (
    echo [OK] Python 3.11 is already installed.
    py -3.11 --version
    echo.
    pause
    exit /b 0
)

set "PY_VER=3.11.9"
set "INSTALLER=%TEMP%\python-%PY_VER%-amd64.exe"
set "URL=https://www.python.org/ftp/python/%PY_VER%/python-%PY_VER%-amd64.exe"

echo [1/3] Downloading Python %PY_VER% installer...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { Invoke-WebRequest -Uri '%URL%' -OutFile '%INSTALLER%' -UseBasicParsing } catch { exit 1 }"

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to download Python installer.
    echo Please check your internet connection.
    echo.
    pause
    exit /b 1
)

echo.
echo [2/3] Installing Python %PY_VER%...
echo This may take a few minutes.
echo.

"%INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1 Include_test=0

if errorlevel 1 (
    echo.
    echo [ERROR] Python installer failed.
    echo Try running this BAT as administrator, or install Python 3.11 manually.
    echo.
    pause
    exit /b 1
)

echo.
echo [3/3] Checking Python 3.11...
py -3.11 --version >nul 2>&1

if errorlevel 1 (
    echo.
    echo [WARN] Python 3.11 was installed, but the py launcher cannot find it yet.
    echo Close this CMD window and open a new one, then run:
    echo.
    echo     py -0p
    echo     py -3.11 --version
    echo.
    pause
    exit /b 0
)

echo.
echo [OK] Python 3.11 is ready.
py -3.11 --version
echo.
echo You can now run setup_venv.bat again.
echo.
pause
exit /b 0