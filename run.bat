@echo off
setlocal

REM Check if venv exists
if not exist .venv (
    echo Virtual environment not found. Running setup...
    call setup.bat
    if errorlevel 1 exit /b 1
)

REM Activate virtual environment
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    echo Try running setup.bat first
    pause
    exit /b 1
)

REM Check for ffmpeg
echo Checking ffmpeg...
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] ffmpeg not found in PATH
    echo Please install ffmpeg and add it to your system PATH
    echo Download from: https://ffmpeg.org/download.html
    echo.
    pause
    exit /b 1
)

REM Run the application
echo Starting VideoCutter...
python app.py

pause