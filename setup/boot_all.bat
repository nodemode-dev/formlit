@echo off
setlocal
cd /d "%~dp0.."
start "formlit engine" cmd /k "cd /d %cd%\backend && boot_backend.bat"
start "formlit frontend" cmd /k "cd /d %cd%\frontend && boot_frontend.bat"
echo [formlit] frontend http://localhost:5390 and engine http://127.0.0.1:8390
