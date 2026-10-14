@echo off
setlocal
cd /d "%~dp0.."
python setup\i18n_review.py %*
