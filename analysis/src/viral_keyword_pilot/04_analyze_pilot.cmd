@echo off
setlocal
cd /d "%~dp0"
.venv\Scripts\python.exe viral_keyword_pilot.py analyze
pause
