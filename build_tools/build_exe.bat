@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion

set "BUILD_TOOLS_DIR=%~dp0"
title 쯔꾸르붕이 Build

echo 쯔꾸르붕이 build
echo.
echo API 번역 단일 실행 파일을 빌드합니다. 런처 EXE는 만들지 않습니다.
echo.
call "%BUILD_TOOLS_DIR%build_game_exe.bat"
exit /b %ERRORLEVEL%
