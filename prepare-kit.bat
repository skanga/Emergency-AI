@echo off
setlocal
REM Survival AI - prepare the kit (REQUIRES INTERNET, run once)
chcp 65001 >nul
cd /d "%~dp0"
set "PY="
set "PY_ARGS="
if exist "%~dp0runtime\python\windows-x86_64\python\python.exe" set "PY=%~dp0runtime\python\windows-x86_64\python\python.exe"
if not defined PY if exist "%~dp0runtime\python\windows-arm64\python\python.exe" set "PY=%~dp0runtime\python\windows-arm64\python\python.exe"
if not defined PY (
  where py >nul 2>nul && (set "PY=py" & set "PY_ARGS=-3")
)
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo.
  echo  Python not found. Install Python 3 from https://www.python.org/downloads/
  echo  ^(check "Add python.exe to PATH"^) and run this file again.
  echo  The preparer can then include portable Python in the kit.
  echo.
  pause
  exit /b 1
)
"%PY%" %PY_ARGS% "%~dp0survival.py" %* prepare
set "RESULT=%ERRORLEVEL%"
pause
exit /b %RESULT%
