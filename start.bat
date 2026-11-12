@echo off
REM Survival AI - start on Windows (double-click)
chcp 65001 >nul
cd /d "%~dp0"
set "PY="
if exist "%~dp0runtime\python\windows-x86_64\python\python.exe" set "PY=%~dp0runtime\python\windows-x86_64\python\python.exe"
if not defined PY if exist "%~dp0runtime\python\windows-arm64\python\python.exe" set "PY=%~dp0runtime\python\windows-arm64\python\python.exe"
if not defined PY (
  where py >nul 2>nul && set "PY=py -3"
)
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo.
  echo  Python not found.
  echo  Run "prepare-kit.bat" online or install Python 3 from https://www.python.org
  echo.
  pause
  exit /b 1
)
%PY% "%~dp0survival.py" %* start
if errorlevel 1 pause
