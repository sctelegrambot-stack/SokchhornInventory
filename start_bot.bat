@echo off
cd /d "%~dp0"
title Sokchhorn Bot
set "PY=%~dp0venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
echo ============================================
echo   Starting Sokchhorn Inventory Bot
echo ============================================
echo.

REM Kill old processes
taskkill /f /im python.exe 2>nul
taskkill /f /im ngrok.exe 2>nul
timeout /t 2 /nobreak >nul

REM Start ngrok tunnel (minimized window)
echo [1/4] Starting ngrok tunnel...
start /MIN "ngrok" ngrok http 5000 --log=stdout
timeout /t 5 /nobreak >nul

REM Fetch URL from ngrok API
echo [2/4] Getting public URL...
set DASHBOARD_URL=
for /f "tokens=*" %%a in ('powershell -Command "try{ $d=curl.exe -s http://127.0.0.1:4040/api/tunnels; $m=[regex]::Match($d,'https://[a-z0-9-]+\.ngrok-free\.(app|dev)'); if($m.Success){ $m.Value + '/' } else { '' } } catch{ '' }"') do set DASHBOARD_URL=%%a

if "%DASHBOARD_URL%"=="" (
    echo [WARN] Could not detect ngrok URL. Check the ngrok window.
    echo.
) else (
    echo [OK] Dashboard URL: %DASHBOARD_URL%
    powershell -NoProfile -Command "$f='%~dp0.env'; $tok=''; $lines=@(); if(Test-Path $f){ $lines=@(Get-Content $f); foreach($l in $lines){ if($l -match '^TELEGRAM_BOT_TOKEN='){ $tok=($l -split '=',2)[1] } } }; if($tok){ $out=@(); foreach($l in $lines){ if($l -match '^TELEGRAM_BOT_TOKEN=' -or $l -match '^DASHBOARD_URL='){ continue }; $out+=$l }; $out+='TELEGRAM_BOT_TOKEN='+$tok; $out+='DASHBOARD_URL=%DASHBOARD_URL%'; Set-Content -Path $f -Value $out -Encoding ASCII } else { Write-Error 'TELEGRAM_BOT_TOKEN not found in .env' }"
    if errorlevel 1 (
        echo [ERROR] TELEGRAM_BOT_TOKEN not set in .env. Add it before starting.
        exit /b 1
    )
)

REM Start Telegram bot
echo [3/4] Starting Telegram bot...
start /B /MIN "" "%PY%" main.py
timeout /t 2 /nobreak >nul

REM Start dashboard
echo [4/4] Starting web dashboard...
echo.
echo ============================================
echo   ACCESS DASHBOARD ON YOUR PHONE:
if "%DASHBOARD_URL%"=="" (
    echo   (check ngrok window for URL)
) else (
    echo   %DASHBOARD_URL%
)
echo.
echo   Login with your admin credentials
echo ============================================
echo.

"%PY%" webapp.py

pause