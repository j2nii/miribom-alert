@echo off
setlocal
cd /d "%~dp0"
call .venv\Scripts\activate.bat
py db_admin.py validate
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%

