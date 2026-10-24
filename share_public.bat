@echo off
title Public Remote Access - Resume Auto-Apply Dashboard
cd /d "C:\Users\infok\.gemini\antigravity\scratch\resume-auto-apply"
echo ================================================================
echo   Creating Worldwide Public HTTPS Link via Cloudflare Tunnel
echo ================================================================
echo.
echo 1. Starting Dashboard Server in background...
start /b "Dashboard" "C:\Users\infok\AppData\Local\Programs\Python\Python312\python.exe" dashboard.py
timeout /t 3 >nul

echo.
echo 2. Launching Secure HTTPS Public Tunnel...
echo Copy the *.trycloudflare.com URL shown below to access from your phone or anywhere:
echo ----------------------------------------------------------------
bin\cloudflared.exe tunnel --url http://127.0.0.1:8000 --no-autoupdate
pause