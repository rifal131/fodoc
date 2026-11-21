@echo off
title FODOC Online Launcher
echo =================================================================
echo   FODOC - Universitas Mercu Buana (AI Face Recognition)
echo   Memulai Backend AI + Cloudflare Tunnel Public
echo =================================================================
echo.
echo [*] Menjalankan Server Backend FastAPI di port 8000...
start "FODOC Backend API" cmd /k "backend\myenv\Scripts\python.exe backend\server.py"
timeout /t 3 /nobreak >nul

echo [*] Membuka Cloudflare Tunnel ke Internet...
start "FODOC Cloudflare Tunnel" cmd /k "backend\cloudflared.exe tunnel --url http://127.0.0.1:8000"

echo.
echo [OK] Backend dan Terowongan Cloudflare sudah aktif!
echo      Lihat link publik HTTPS di jendela 'FODOC Cloudflare Tunnel'.
echo =================================================================
pause
