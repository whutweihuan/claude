@echo off
cd /d "%~dp0"
python share_app.py
if errorlevel 1 pause
