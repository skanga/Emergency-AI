@echo off
REM Compatibility shortcut. Prefer start.bat prepare.
call "%~dp0start.bat" prepare %*
exit /b %ERRORLEVEL%
