@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "LITE="
set "OPEN=0"
for %%A in (%*) do (
  if /i "%%~A"=="--lite" ( set "LITE=--lite" ) else if /i "%%~A"=="--open" ( set "OPEN=1" ) else if /i "%%~A"=="--help" ( goto :usage ) else if /i "%%~A"=="-h" ( goto :usage ) else ( call :usage & exit /b 2 )
)

echo.
echo [formlit] == checking the tools
where python >nul 2>nul || ( echo [formlit] Python 3.12 or newer is needed: https://www.python.org/downloads/ & exit /b 1 )
where node >nul 2>nul || ( echo [formlit] Node 22 or newer is needed: https://nodejs.org & exit /b 1 )
where cargo >nul 2>nul || ( echo [formlit] Rust is needed: https://rustup.rs & exit /b 1 )
for /f "tokens=1 delims=." %%V in ('node -p "process.versions.node"') do if %%V LSS 22 ( echo [formlit] Node 22 or newer is needed, this is Node %%V: https://nodejs.org & exit /b 1 )

echo.
echo [formlit] == installing the engine and the window
call setup\install_all.bat %LITE% || goto :failed

echo.
echo [formlit] == installing the desktop packages and checking the Tauri toolchain
call setup\install_desktop.bat || goto :failed

echo.
echo [formlit] == building the window, freezing the engine and building the desktop app
echo [formlit] the first build compiles several hundred Rust crates
call setup\desktop_build.bat || goto :failed

echo.
echo [formlit] done. The installers are in src-tauri\target\release\bundle (msi and nsis)
if "%OPEN%"=="1" start "" "src-tauri\target\release\bundle"
exit /b 0

:failed
echo.
echo [formlit] the build stopped at the step above; fix what it says and run build_app.bat again
exit /b 1

:usage
echo build_app.bat           build formlit's desktop app on Windows, start to finish
echo   --lite                skip the AI extra (AI masks, Remove and Denoise fetch their models on first use)
echo   --open                open the folder with the installers when the build is done
exit /b 0
