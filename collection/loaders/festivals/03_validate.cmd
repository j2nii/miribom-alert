@echo off
setlocal
cd /d "%~dp0"
mysql -u yaho_loader -p tour_earlywarning ^< 03_validate.sql
pause

