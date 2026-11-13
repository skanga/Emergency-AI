@echo off
REM Compatibility shortcut. Prefer run.bat prepare.
call "%~dp0run.bat" prepare %*
exit /b %ERRORLEVEL%
