@echo off
setlocal
cd /d "%~dp0.."
set "LITE=0"
if /i "%~1"=="--lite" set "LITE=1"
echo [formlit] installing the engine
pushd backend
call oc_install.bat || ( popd & exit /b 1 )
popd
if "%LITE%"=="1" ( echo [formlit] skipping the AI extra, models are fetched on first use ) else ( call setup\install_ml.bat || echo [formlit] the AI extra did not install, retry with formlit.bat install-ml )
echo [formlit] installing the frontend
pushd frontend
call oc_install.bat || ( popd & exit /b 1 )
popd
echo [formlit] done. Boot with formlit.bat
