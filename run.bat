@echo off
title Trading Bot — Start
chcp 65001 >nul

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║         Trading Bot — Starting...        ║
echo  ╚══════════════════════════════════════════╝
echo.
echo  Backend  aur Frontend dono khul rahe hain...
echo.

start "Trading — Backend"  cmd /k "cd /d "%~dp0backend"  && python -m uvicorn app.main:app --reload --port 8000"
timeout /t 4 /nobreak >nul
start "Trading — Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"
timeout /t 6 /nobreak >nul
start http://localhost:5173

echo  Done! Browser mein http://localhost:5173 khul gaya.
echo  Dono CMD windows band MAT karna.
echo.
pause
