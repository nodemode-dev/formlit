@echo off
setlocal
cd /d "%~dp0.."
if not exist frontend\dist\index.html call setup\build_frontend.bat
set "FORMLIT_DIST=%cd%\frontend\dist"
cd backend
if not exist venv\Scripts\activate.bat ( echo [formlit] engine venv missing, run formlit.bat install & exit /b 1 )
call venv\Scripts\activate.bat
if not defined FORMLIT_HOST set "FORMLIT_HOST=127.0.0.1"
if not defined FORMLIT_PORT set "FORMLIT_PORT=8390"
echo [formlit] serving http://%FORMLIT_HOST%:%FORMLIT_PORT%
uvicorn app.main:app --host %FORMLIT_HOST% --port %FORMLIT_PORT%
