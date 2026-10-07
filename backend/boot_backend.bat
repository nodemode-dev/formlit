@echo off
setlocal
cd /d "%~dp0"
if not exist venv\Scripts\activate.bat ( echo [formlit] engine venv missing, run formlit.bat install & exit /b 1 )
call venv\Scripts\activate.bat
if not defined FORMLIT_HOST set "FORMLIT_HOST=127.0.0.1"
if not defined FORMLIT_PORT set "FORMLIT_PORT=8390"
uvicorn app.main:app --reload --reload-dir app --host %FORMLIT_HOST% --port %FORMLIT_PORT%
