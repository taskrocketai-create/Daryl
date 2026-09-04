@echo off
setlocal

REM Always run from this file's own folder, regardless of where the
REM shortcut that launches it actually lives (Desktop, taskbar, etc.)
cd /d "%~dp0"

if not exist ".env" (
    echo ============================================
    echo   .env file not found!
    echo.
    echo   Someone needs to copy .env.example to .env
    echo   and fill in the real API keys before Daryl
    echo   can start.
    echo ============================================
    echo.
    pause
    exit /b 1
)

:start
echo ============================================
echo   Starting Daryl...
echo ============================================
echo.
python main.py

echo.
echo ============================================
echo   Daryl stopped (crashed or was closed).
echo   Restarting automatically in 5 seconds...
echo   Close this window instead if you want him
echo   to stay off.
echo ============================================
timeout /t 5 /nobreak >nul
goto start
