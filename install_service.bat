@echo off
REM MT5 AI Trader - Windows Service Setup Script
REM Run as Administrator

setlocal enabledelayedexpansion

echo.
echo ===================================================
echo MT5 AI Trader - Windows Service Installation
echo ===================================================
echo.

REM Check if running as admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: This script must be run as Administrator!
    echo Please run Command Prompt as Administrator and try again.
    pause
    exit /b 1
)

REM Get script directory
set SCRIPT_DIR=%~dp0
cd /d %SCRIPT_DIR%..

echo Current Directory: %cd%
echo.

REM Check if virtual environment exists
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found at .venv\Scripts\python.exe
    echo Please run: python -m venv .venv
    echo Then run: .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM Check if main.py exists
if not exist "mt5_ai_trader\main.py" (
    echo ERROR: main.py not found!
    pause
    exit /b 1
)

echo ✓ Environment checks passed
echo.

REM Download NSSM if not present
if not exist "deploy\nssm.exe" (
    echo Downloading NSSM (Non-Sucking Service Manager)...
    powershell -Command "Invoke-WebRequest -Uri 'https://nssm.cc/download/nssm-2.24-101-g897c7ad.zip' -OutFile 'nssm.zip'" 2>nul
    if %errorLevel% equ 0 (
        powershell -Command "Expand-Archive -Path 'nssm.zip' -DestinationPath 'deploy' -Force" 2>nul
        move deploy\nssm-2.24-101-g897c7ad\win64\nssm.exe deploy\nssm.exe >nul
        rmdir /s /q deploy\nssm-2.24-101-g897c7ad 2>nul
        del nssm.zip
        echo ✓ NSSM downloaded
    ) else (
        echo.
        echo WARNING: Could not download NSSM automatically
        echo Please download manually from: https://nssm.cc/download
        echo Extract nssm.exe to the deploy\ folder
        pause
        exit /b 1
    )
) else (
    echo ✓ NSSM already available
)

echo.

REM Service configuration
set SERVICE_NAME=MT5Trader
set PYTHON_EXE=%cd%\.venv\Scripts\python.exe
set BOT_SCRIPT=%cd%\deploy\start_bot.py
set LOG_DIR=%cd%\logs
set APP_DIR=%cd%

mkdir %LOG_DIR% 2>nul

echo Service Configuration:
echo   Service Name: %SERVICE_NAME%
echo   Python: %PYTHON_EXE%
echo   Bot Script: %BOT_SCRIPT%
echo   App Dir: %APP_DIR%
echo   Logs: %LOG_DIR%
echo.

REM Check if service already exists
sc query %SERVICE_NAME% >nul 2>&1
if %errorLevel% equ 0 (
    echo Service '%SERVICE_NAME%' already exists.
    echo Removing old service...
    net stop %SERVICE_NAME% >nul 2>&1
    deploy\nssm.exe remove %SERVICE_NAME% confirm
    echo ✓ Old service removed
    echo.
)

REM Install service
echo Installing service...
deploy\nssm.exe install %SERVICE_NAME% "%PYTHON_EXE%" "%BOT_SCRIPT%"

if %errorLevel% neq 0 (
    echo ERROR: Failed to install service!
    pause
    exit /b 1
)

echo ✓ Service installed

REM Configure service
echo Configuring service...
deploy\nssm.exe set %SERVICE_NAME% AppDirectory "%APP_DIR%"
deploy\nssm.exe set %SERVICE_NAME% AppStdout "%LOG_DIR%\service.log"
deploy\nssm.exe set %SERVICE_NAME% AppStderr "%LOG_DIR%\service_error.log"
deploy\nssm.exe set %SERVICE_NAME% AppRotateFiles 1
deploy\nssm.exe set %SERVICE_NAME% AppRotateOnline 1
deploy\nssm.exe set %SERVICE_NAME% AppRotateSeconds 86400
deploy\nssm.exe set %SERVICE_NAME% AppRotateBytes 10485760
deploy\nssm.exe set %SERVICE_NAME% Start SERVICE_AUTO_START
deploy\nssm.exe set %SERVICE_NAME% Type SERVICE_WIN32_OWN_PROCESS
deploy\nssm.exe set %SERVICE_NAME% Priority ABOVE_NORMAL

echo ✓ Service configured

REM Start service
echo.
echo Starting service...
net start %SERVICE_NAME%

if %errorLevel% equ 0 (
    echo ✅ Service started successfully!
    echo.
    echo ========================================
    echo Service Installation Complete!
    echo ========================================
    echo.
    echo Commands:
    echo   Start:   net start %SERVICE_NAME%
    echo   Stop:    net stop %SERVICE_NAME%
    echo   Status:  sc query %SERVICE_NAME%
    echo   Restart: net stop %SERVICE_NAME% ^& net start %SERVICE_NAME%
    echo   Remove:  nssm.exe remove %SERVICE_NAME% confirm
    echo.
    echo Log files:
    echo   App Log:   %LOG_DIR%\service.log
    echo   Error Log: %LOG_DIR%\service_error.log
    echo   Bot Log:   %LOG_DIR%\bot_runner.log
    echo.
) else (
    echo ❌ Failed to start service
    echo Check logs for details: %LOG_DIR%\service_error.log
    pause
    exit /b 1
)

pause
