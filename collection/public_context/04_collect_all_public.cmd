@echo off
setlocal
cd /d "%~dp0"
call .venv\Scripts\activate.bat
py collect_public_context.py all
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%

