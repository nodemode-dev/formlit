@echo off
setlocal
cd /d "%~dp0.."
set "FAIL=0"
where node >nul 2>nul && ( echo   ok     node ) || ( echo   FAIL   node, install Node 22 LTS & set "FAIL=1" )
where npm >nul 2>nul && ( echo   ok     npm ) || ( echo   FAIL   npm & set "FAIL=1" )
where py >nul 2>nul && ( echo   ok     python launcher ) || ( where python >nul 2>nul && ( echo   ok     python ) || ( echo   FAIL   Python 3.12+ is required & set "FAIL=1" ) )
if exist backend\venv\Scripts\activate.bat ( echo   ok     engine venv ) else ( echo   warn   engine venv, run formlit.bat install )
if exist frontend\node_modules ( echo   ok     frontend node_modules ) else ( echo   warn   frontend deps, run formlit.bat install )
where ffmpeg >nul 2>nul && ( echo   ok     ffmpeg for slideshow video ) || ( echo   warn   ffmpeg, slideshows export as PDF only )
where cargo >nul 2>nul && ( echo   ok     rust for desktop builds ) || ( echo   warn   rust, desktop builds need https://rustup.rs )
exit /b %FAIL%
