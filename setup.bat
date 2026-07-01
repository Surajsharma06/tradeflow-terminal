@echo off
title Trading Bot — Windows Setup
color 0A
chcp 65001 >nul

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║      Trading Bot — Windows Setup         ║
echo  ║   Pehli baar chalao, sirf ek baar        ║
echo  ╚══════════════════════════════════════════╝
echo.

:: ── Check Python ──────────────────────────────────────────────
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo  [ERROR] Python nahi mila!
    echo.
    echo  Yahan se install karo:
    echo  https://www.python.org/downloads/
    echo.
    echo  ZAROOR: Install karte waqt
    echo  "Add Python to PATH" wala box tick karna!
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo  [OK] %%i mila

:: ── Check Node.js ─────────────────────────────────────────────
node --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo  [ERROR] Node.js nahi mila!
    echo.
    echo  Yahan se install karo:
    echo  https://nodejs.org  (LTS version lo)
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version') do echo  [OK] Node.js %%i mila
echo.

:: ── Step 1: Backend packages ───────────────────────────────────
echo  [1/4] Backend Python packages install ho rahe hain...
echo        (3-5 min lag sakte hain, internet speed ke hisaab se)
echo.
pip install fastapi "uvicorn[standard]" pydantic pydantic-settings ^
    httpx python-dotenv pytz python-dateutil ^
    pandas numpy yfinance ^
    xgboost scikit-learn ^
    redis sqlalchemy aiosqlite ^
    apscheduler websockets aiofiles python-multipart ^
    --quiet --no-warn-script-location

IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo  [ERROR] Backend install mein problem aayi.
    echo  Internet check karo aur dobara chalao.
    pause
    exit /b 1
)
echo  [OK] Backend packages ready!
echo.

:: ── Step 2: Frontend packages ─────────────────────────────────
echo  [2/4] Frontend Node.js packages install ho rahe hain...
echo        (1-2 min)
echo.
cd /d "%~dp0frontend"
call npm install --silent 2>nul
IF %ERRORLEVEL% NEQ 0 (
    call npm install
)
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo  [ERROR] Frontend install mein problem aayi.
    pause
    exit /b 1
)
echo  [OK] Frontend packages ready!
echo.

:: ── Step 3: Folders aur .env ──────────────────────────────────
echo  [3/4] Folders aur config file bana raha hoon...
cd /d "%~dp0"
if not exist "data"              mkdir "data"
if not exist "data\signals"      mkdir "data\signals"
if not exist "data\backtest"     mkdir "data\backtest"
if not exist "backend\app\ml\models" mkdir "backend\app\ml\models"

if not exist "backend\.env" (
    echo TWELVE_DATA_API_KEY=1e2375a26d8e4836bbd4d1ac4cacca9d > "backend\.env"
    echo FINNHUB_API_KEY=d91bn9pr01qv4dr2m8e0d91bn9pr01qv4dr2m8eg >> "backend\.env"
    echo DATABASE_URL=sqlite+aiosqlite:///./trading.db >> "backend\.env"
    echo  [OK] .env file banayi
) else (
    echo  [OK] .env file pehle se hai
)
echo.

:: ── Step 4: Launch ───────────────────────────────────────────
echo  [4/4] Servers start ho rahe hain...
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║  Backend  : http://localhost:8000        ║
echo  ║  Frontend : http://localhost:5173        ║
echo  ║                                          ║
echo  ║  Browser mein kholo:                     ║
echo  ║  http://localhost:5173                   ║
echo  ║                                          ║
echo  ║  Dono CMD windows band MAT karna!        ║
echo  ╚══════════════════════════════════════════╝
echo.

start "Trading — Backend" cmd /k "cd /d "%~dp0backend" && python -m uvicorn app.main:app --reload --port 8000"
timeout /t 4 /nobreak >nul
start "Trading — Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"
timeout /t 6 /nobreak >nul
start http://localhost:5173

echo  Setup complete! Browser ab khul gaya hoga.
echo.
pause
