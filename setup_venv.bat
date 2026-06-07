@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul

REM ==========================================================
REM  쯔꾸르붕이 - Setup Source/Build venv
REM  - 반드시 이 BAT가 있는 프로젝트 루트의 .venv를 만든다.
REM  - 실행(run.bat)과 빌드(build_tools\build_game_exe.bat)는 이 .venv만 사용한다.
REM  - 기준 Python: 3.11.x
REM ==========================================================

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%" || goto FAIL_ROOT

set "APP_ROOT=%CD%"
set "VENV_DIR=%APP_ROOT%\.venv"
set "PY=%VENV_DIR%\Scripts\python.exe"

echo ==================================================
echo 쯔꾸르붕이 - Setup Source/Build venv ^(Python 3.11 only^)
echo ==================================================
echo Project root : %APP_ROOT%
echo Venv path    : %VENV_DIR%
echo.
echo 이 셋업은 실행과 빌드가 같이 쓰는 상위 폴더 .venv를 만듭니다.
echo build_tools 안쪽이나 다른 위치에 별도 .venv를 만들지 않습니다.
echo.

if not exist "main.py" (
    echo [ERROR] main.py not found in project root.
    goto FAIL
)
if not exist "ysb\__init__.py" (
    echo [ERROR] ysb package not found in project root.
    goto FAIL
)

if exist "%PY%" (
    echo Existing .venv found.
    "%PY%" -c "import sys; print('Existing venv Python:', sys.version); raise SystemExit(0 if sys.version_info[:2] == (3,11) else 1)"
    if errorlevel 1 (
        echo.
        echo [WARN] Existing .venv is not Python 3.11.x. It must be recreated.
        set "FORCE_RECREATE=1"
    ) else (
        echo.
        choice /C YN /N /M "Recreate .venv anyway? [Y/N]: "
        if errorlevel 2 (
            echo.
            echo Keeping existing .venv. Requirements will be refreshed.
            goto INSTALL_REQS
        )
        set "FORCE_RECREATE=1"
    )
)

if defined FORCE_RECREATE (
    echo.
    echo Removing existing .venv...
    rmdir /S /Q "%VENV_DIR%"
    if exist "%VENV_DIR%" (
        echo [ERROR] Failed to remove .venv. Close running Python/쯔꾸르붕이 windows and retry.
        goto FAIL
    )
)

if not exist "%PY%" (
    echo.
    echo [1/7] Creating clean root .venv with Python 3.11...
    py -3.11 -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create .venv with py -3.11.
        echo Run install_python311.bat first, or install Python 3.11.x manually.
        goto FAIL
    )
)

:INSTALL_REQS
set "PY=%VENV_DIR%\Scripts\python.exe"

echo.
echo [2/7] Python path/version check
"%PY%" -c "import sys, pathlib; print('sys.executable =', sys.executable); print('version        =', sys.version); raise SystemExit(0 if sys.version_info[:2] == (3,11) else 1)"
if errorlevel 1 (
    echo [ERROR] Root .venv is not Python 3.11.x.
    goto FAIL
)

echo.
echo [3/7] Upgrade pip / wheel / base pins
"%PY%" -m pip install --upgrade "pip<26" wheel --prefer-binary
if errorlevel 1 goto FAIL
"%PY%" -m pip install "setuptools==81.0.0" "numpy==1.26.4" --force-reinstall --prefer-binary
if errorlevel 1 goto FAIL

echo.
echo [4/7] Install app requirements
if exist "requirements\common.txt" (
    echo Installing requirements\common.txt
    "%PY%" -m pip install -r "requirements\common.txt" --prefer-binary
    if errorlevel 1 goto FAIL
) else (
    echo [ERROR] requirements\common.txt not found.
    goto FAIL
)

if exist "requirements\app.txt" (
    echo Installing requirements\app.txt
    "%PY%" -m pip install -r "requirements\app.txt" --prefer-binary
    if errorlevel 1 goto FAIL
) else if exist "requirements\lite.txt" (
    echo Installing requirements\lite.txt
    "%PY%" -m pip install -r "requirements\lite.txt" --prefer-binary
    if errorlevel 1 goto FAIL
) else (
    echo [ERROR] requirements\app.txt not found.
    goto FAIL
)

if exist "requirements\build.txt" (
    echo Installing requirements\build.txt
    "%PY%" -m pip install -r "requirements\build.txt" --prefer-binary
    if errorlevel 1 goto FAIL
) else (
    echo [WARN] requirements\build.txt not found. Installing PyInstaller directly.
    "%PY%" -m pip install pyinstaller --prefer-binary
    if errorlevel 1 goto FAIL
)

echo.
echo [5/7] Re-pin compatible base versions after installs
"%PY%" -m pip install "setuptools==81.0.0" "numpy==1.26.4" --force-reinstall --prefer-binary
if errorlevel 1 goto FAIL

echo.
echo [6/7] Verify imports
"%PY%" -c "import sys; print('python', sys.version)"
if errorlevel 1 goto FAIL
"%PY%" -c "import numpy; print('numpy', numpy.__version__)"
if errorlevel 1 goto FAIL
"%PY%" -c "import PyQt6; print('PyQt6 OK')"
if errorlevel 1 goto FAIL
"%PY%" -c "import cv2; print('cv2 OK')"
if errorlevel 1 goto FAIL
"%PY%" -c "import PIL; print('Pillow OK')"
if errorlevel 1 goto FAIL
"%PY%" -c "import requests, openai; print('translation API runtime OK')"
if errorlevel 1 goto FAIL
"%PY%" -c "import PyInstaller; print('PyInstaller OK')"
if errorlevel 1 goto FAIL

echo.
echo [7/7] Done
echo ==================================================
echo 쯔꾸르붕이 source/build venv setup finished successfully.
echo Root .venv will be used by:
echo   run.bat
echo   build_tools\build_game_exe.bat
echo ==================================================
echo.
pause
exit /b 0

:FAIL_ROOT
echo [ERROR] Failed to enter script directory.
goto FAIL

:FAIL
echo.
echo ==================================================
echo [ERROR] Setup failed. Please capture the error above.
echo ==================================================
echo.
pause
exit /b 1
