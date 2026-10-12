@echo off
REM Activate your virtual environment first.
cd /d "%~dp0"
python install.py %*
exit /b %errorlevel%
