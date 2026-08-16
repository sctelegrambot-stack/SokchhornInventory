@echo off
cd /d "%~dp0"
title Sokchhorn Bot - Setup
echo ============================================
echo   Sokchhorn Inventory Bot - Spare PC Setup
echo ============================================
echo.
echo Step 1: Creating virtual environment...
if exist venv\Scripts\python.exe (
    echo [OK] venv already exists.
) else (
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Could not create venv. Make sure Python is installed.
        pause
        exit /b 1
    )
    echo [OK] venv created.
)
echo.
echo Step 2: Installing Python packages...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] pip install failed. Check your internet connection.
    pause
    exit /b 1
)
echo [OK] Packages installed.
echo.
echo Step 3: Creating exports folder...
if not exist exports mkdir exports
echo [OK] Exports folder ready.
echo.
echo Step 4: Checking TELEGRAM_BOT_TOKEN...
if not exist .env (
    echo [WARN] No .env file found. Copy .env from the main PC or create one with:
    echo   TELEGRAM_BOT_TOKEN=your_token_here
    echo   DASHBOARD_URL=http://localhost:5000
) else (
    echo [OK] .env file found.
)
echo.
echo Step 5: Downloading ngrok...
where ngrok >nul 2>nul
if %errorlevel% equ 0 (
    echo [OK] ngrok already installed.
) else (
    echo Downloading ngrok...
    powershell -Command "Invoke-WebRequest -Uri 'https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip' -OutFile '%TEMP%\ngrok.zip'; Expand-Archive '%TEMP%\ngrok.zip' -DestinationPath '%~dp0' -Force; Remove-Item '%TEMP%\ngrok.zip'"
    echo [OK] ngrok downloaded to project folder.
)
echo.
echo Step 6: Configuring ngrok authtoken...
set NGROK_AUTHTOKEN=
set /p NGROK_AUTHTOKEN=Enter your ngrok authtoken (https://dashboard.ngrok.com/get-started/your-authtoken) or press Enter to skip: 
if not "%NGROK_AUTHTOKEN%"=="" (
    ngrok config add-authtoken %NGROK_AUTHTOKEN%
    echo [OK] ngrok authtoken configured.
) else (
    echo [SKIP] No authtoken set. ngrok tunnels will not open until you configure one.
)
echo.
echo ============================================
echo   SETUP COMPLETE!
echo ============================================
echo.
echo To start: Double-click start_bot.bat
echo.
echo The bot will start, ngrok will create a public URL,
echo and the dashboard will be accessible from anywhere.
echo.
pause