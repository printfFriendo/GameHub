@echo off
echo Starting GameHub Scraper Application...
echo.

REM Set PATH to include Python from PATH environment variable
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    python main.py
) else (
    echo Python not found in PATH. Please install Python 3.12+ from python.org
    pause
)
