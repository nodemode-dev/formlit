@echo off
setlocal
cd /d "%~dp0..\backend"
if not exist venv\Scripts\activate.bat ( echo [formlit] engine venv missing, run formlit.bat install & exit /b 1 )
call venv\Scripts\activate.bat
pip install -r requirements_ml.txt || exit /b 1
echo [formlit] AI extras ready; each model downloads on first use, pinned to its SHA-256
