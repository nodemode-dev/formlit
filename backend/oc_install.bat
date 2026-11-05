@echo off
setlocal
cd /d "%~dp0"
set "PY="
for %%V in (3.14 3.13 3.12) do if not defined PY ( py -%%V -c "import sys" >nul 2>nul && set "PY=py -%%V" )
if not defined PY ( python -c "import sys; raise SystemExit(0 if (3, 12) <= sys.version_info[:2] <= (3, 14) else 1)" >nul 2>nul && set "PY=python" )
if not defined PY ( echo [formlit] Python 3.12, 3.13 or 3.14 is required & exit /b 1 )
if not exist venv %PY% -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
