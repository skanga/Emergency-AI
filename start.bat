@echo off
setlocal
REM Emergency AI - start on Windows (double-click)
chcp 65001 >nul
cd /d "%~dp0"
set "PY="
set "PY_ARGS="
set "KIT_ARCH=x86_64"
if /i "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "KIT_ARCH=arm64"
if /i "%PROCESSOR_ARCHITEW6432%"=="ARM64" set "KIT_ARCH=arm64"
if exist "%~dp0runtime\python\windows-%KIT_ARCH%\python\python.exe" set "PY=%~dp0runtime\python\windows-%KIT_ARCH%\python\python.exe"
if not defined PY if exist "%~dp0runtime\python\windows-x86_64\python\python.exe" set "PY=%~dp0runtime\python\windows-x86_64\python\python.exe"
if not defined PY (
  where py >nul 2>nul && (set "PY=py" & set "PY_ARGS=-3")
)
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo.
  echo  Python not found.
  echo  Install Python 3.8+ from https://www.python.org/downloads/ and enable "Add python.exe to PATH".
  echo  Or copy a kit containing portable Python for this computer. Then run start.bat again.
  echo.
  pause
  exit /b 1
)
"%PY%" %PY_ARGS% "%~dp0survival.py" %*
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" pause
exit /b %RESULT%
