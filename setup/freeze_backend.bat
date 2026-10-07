@echo off
setlocal
cd /d "%~dp0.."
set "ROOT=%cd%"
if not exist backend\venv\Scripts\activate.bat ( echo [formlit] engine venv missing, run formlit.bat install & exit /b 1 )
call backend\venv\Scripts\activate.bat
python -c "import PyInstaller" >nul 2>nul || ( echo [formlit] PyInstaller missing, run formlit.bat install-desktop & exit /b 1 )
if defined FORMLIT_TARGET ( set "TRIPLE=%FORMLIT_TARGET%" ) else ( for /f "tokens=2" %%t in ('rustc -vV ^| findstr /b "host:"') do set "TRIPLE=%%t" )
if not defined TRIPLE ( echo [formlit] rustc not found, install Rust or set FORMLIT_TARGET & exit /b 1 )
if not exist frontend\dist\index.html call setup\build_frontend.bat
cd backend
if exist build\pyinstaller rmdir /s /q build\pyinstaller
if exist dist-engine rmdir /s /q dist-engine
pyinstaller --noconfirm --clean --onefile --name formlit-engine --distpath dist-engine --workpath build\pyinstaller --specpath build\pyinstaller --add-data "%ROOT%\frontend\dist;frontend_dist" --add-data "%ROOT%\shared;shared" --collect-submodules app --collect-submodules uvicorn --collect-all rawpy --collect-all llvmlite --collect-submodules numba --hidden-import cv2 --collect-all reportlab --collect-all onnxruntime --hidden-import tifffile --exclude-module pillow_heif "%ROOT%\backend\formlit_engine.py" || exit /b 1
if not exist "%ROOT%\src-tauri\binaries" mkdir "%ROOT%\src-tauri\binaries"
copy /y dist-engine\formlit-engine.exe "%ROOT%\src-tauri\binaries\formlit-engine-%TRIPLE%.exe" >nul
"%ROOT%\src-tauri\binaries\formlit-engine-%TRIPLE%.exe" --selfcheck
