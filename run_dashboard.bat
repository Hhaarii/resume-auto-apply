@echo off
title Resume Auto-Apply Dashboard
cd /d "C:\Users\infok\.gemini\antigravity\scratch\resume-auto-apply"
echo ================================================================
echo   Resume Auto-Updater & Application Co-Pilot Dashboard
echo ================================================================
echo.
echo [1] Standard Mode  (Accessible on this PC + Phone on same Wi-Fi)
echo [2] Worldwide Mode (Generates public HTTPS link for anywhere access)
echo.
set /p choice="Choose [1] or [2] (Default is 1): "

if "%choice%"=="2" (
    echo.
    echo Starting Dashboard with Cloudflare Public Tunnel (No account needed)...
    call share_public.bat
) else (
    echo.
    echo [*] Local:      http://localhost:8000
    echo [*] Your Phone: http://192.168.1.47:8000
    echo.
    start http://localhost:8000
    "C:\Users\infok\AppData\Local\Programs\Python\Python312\python.exe" dashboard.py
)

pause
