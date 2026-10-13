@echo off
setlocal
cd /d "%~dp0"
set "CMD=%~1"
set "ARG=%~2"
if "%CMD%"=="" set "CMD=boot"
if /i "%CMD%"=="boot" ( call setup\boot_all.bat & goto :eof )
if /i "%CMD%"=="dev" ( call setup\boot_all.bat & goto :eof )
if /i "%CMD%"=="install" ( call setup\install_all.bat %ARG% & goto :eof )
if /i "%CMD%"=="install-ml" ( call setup\install_ml.bat & goto :eof )
if /i "%CMD%"=="install-desktop" ( call setup\install_desktop.bat & goto :eof )
if /i "%CMD%"=="backend" ( call setup\boot_backend.bat & goto :eof )
if /i "%CMD%"=="frontend" ( call setup\boot_frontend.bat & goto :eof )
if /i "%CMD%"=="build" ( call setup\build_frontend.bat & goto :eof )
if /i "%CMD%"=="serve" ( call setup\serve.bat & goto :eof )
if /i "%CMD%"=="freeze" ( call setup\freeze_backend.bat & goto :eof )
if /i "%CMD%"=="desktop" (
  if /i "%ARG%"=="build" ( call setup\desktop_build.bat ) else ( call setup\desktop_dev.bat )
  goto :eof
)
if /i "%CMD%"=="mcp" ( python setup\mcp_stdio.py & goto :eof )
if /i "%CMD%"=="claude" ( python setup\claude_launch.py %2 %3 %4 %5 %6 %7 %8 %9 & goto :eof )
if /i "%CMD%"=="agents" (
  if exist backend\venv\Scripts\python.exe ( backend\venv\Scripts\python.exe setup\agents.py %2 %3 %4 %5 ) else ( python setup\agents.py %2 %3 %4 %5 )
  goto :eof
)
if /i "%CMD%"=="cli" ( python setup\cli.py %2 %3 %4 %5 %6 %7 %8 %9 & goto :eof )
if /i "%CMD%"=="doctor" ( call setup\doctor.bat & goto :eof )
if /i "%CMD%"=="counts" ( call setup\counts.bat %ARG% & goto :eof )
if /i "%CMD%"=="clean" ( call setup\clean.bat %ARG% & goto :eof )
if /i "%CMD%"=="help" ( call :usage & exit /b 0 )
echo [formlit] unknown command: %CMD%
call :usage
exit /b 2
:usage
echo formlit.bat [command]
echo   boot ^| install [--lite] ^| install-ml ^| install-desktop ^| backend ^| frontend
echo   build ^| serve ^| freeze ^| desktop dev ^| desktop build ^| mcp ^| claude [args] ^| agents install^|sync ^| cli ^| doctor ^| counts ^| clean [--all] ^| help
exit /b 0
