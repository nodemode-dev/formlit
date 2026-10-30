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
set "PYTHONPATH=%ROOT%\backend;%PYTHONPATH%"
pyinstaller --noconfirm --clean --onefile --name formlit-engine --distpath dist-engine --workpath build\pyinstaller --specpath build\pyinstaller --paths "%ROOT%\backend" --add-data "%ROOT%\frontend\dist;frontend_dist" --add-data "%ROOT%\shared;shared" --hidden-import app.engine.cmd_library --hidden-import app.engine.cmd_develop --hidden-import app.engine.presets --hidden-import app.engine.cmd_ai --hidden-import app.engine.cmd_output --hidden-import app.engine.agents --hidden-import app.engine.cmd_terminal --hidden-import app.engine.claude_code --hidden-import app.engine.cmd_analyze --hidden-import app.engine.preset_library --hidden-import app.engine.cmd_workflow --hidden-import app.engine.cmd_templates --hidden-import app.engine.cmd_chat --hidden-import app.engine.template_library --hidden-import app.output.export_library --hidden-import app.routers.mcp_workflows --collect-all winpty --hidden-import app.output.services.webdav --hidden-import app.output.services.s3 --collect-submodules uvicorn --collect-all rawpy --collect-all llvmlite --collect-submodules numba --hidden-import cv2 --collect-all reportlab --collect-all onnxruntime --hidden-import tifffile --collect-all imagecodecs --collect-submodules app --collect-submodules paramiko --collect-all pikepdf --exclude-module pillow_heif "%ROOT%\backend\formlit_engine.py" || exit /b 1
dist-engine\formlit-engine.exe --selfcheck || ( echo [formlit] the frozen engine failed its selfcheck; nothing was copied to src-tauri\binaries & exit /b 1 )
if not exist "%ROOT%\src-tauri\binaries" mkdir "%ROOT%\src-tauri\binaries"
copy /y dist-engine\formlit-engine.exe "%ROOT%\src-tauri\binaries\formlit-engine-%TRIPLE%.exe" >nul || exit /b 1
