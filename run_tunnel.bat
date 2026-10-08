@echo off
setlocal
title Cloudflare Secure Tunnel
echo ========================================================
echo   Starting Cloudflare Tunnel to Local Backend (Port 8000)
echo ========================================================
echo Tunggu beberapa detik sampai muncul URL publik:
echo misal: https://xxxx-xxxx-xxxx.trycloudflare.com
echo.
echo Salin URL tersebut ke antarmuka Hugging Face Spaces!
echo ========================================================
echo.

set "CF_PATH="

where cloudflared >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    cloudflared tunnel --url http://127.0.0.1:8000
    goto :end
)

if exist "C:\Program Files (x86)\cloudflared\cloudflared.exe" (
    set CF_PATH="C:\Program Files (x86)\cloudflared\cloudflared.exe"
    goto :run_cf
)

if exist "C:\Program Files\cloudflared\cloudflared.exe" (
    set CF_PATH="C:\Program Files\cloudflared\cloudflared.exe"
    goto :run_cf
)

echo [!] Cloudflared tidak ditemukan. Silakan jalankan manual di terminal:
echo     cloudflared tunnel --url http://127.0.0.1:8000
pause
goto :end

:run_cf
%CF_PATH% tunnel --url http://127.0.0.1:8000

:end
