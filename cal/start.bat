@echo off
rem Double-click this file to launch the calculator.
cd /d %~dp0
python main.py
if errorlevel 1 (
    echo.
    echo Failed to launch the calculator.
    echo Make sure Python is installed and on your PATH.
    pause
)
