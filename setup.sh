#!/bin/bash

echo "============================================"
echo "   Trading System - Mac Setup"
echo "============================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 nahi mila!"
    echo "Install karo: https://python.org/downloads"
    exit 1
fi

# Check Node
if ! command -v node &> /dev/null; then
    echo "[ERROR] Node.js nahi mila!"
    echo "Install karo: https://nodejs.org"
    exit 1
fi

echo "[OK] Python aur Node.js mil gaye!"
echo ""

# Get script directory (works from anywhere)
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Install backend packages
echo "[1/4] Backend packages install ho rahe hain... (2-3 min)"
pip3 install fastapi uvicorn pydantic pydantic-settings httpx python-dotenv pytz pandas numpy yfinance apscheduler websockets aiofiles python-multipart python-dateutil --quiet --user

if [ $? -ne 0 ]; then
    echo "[ERROR] Backend install mein problem aayi."
    exit 1
fi
echo "[OK] Backend packages ready!"
echo ""

# Install frontend packages
echo "[2/4] Frontend packages install ho rahe hain... (1-2 min)"
cd "$DIR/frontend"
npm install --silent

if [ $? -ne 0 ]; then
    echo "[ERROR] Frontend install mein problem aayi."
    exit 1
fi
echo "[OK] Frontend packages ready!"
echo ""

# Create required folders
echo "[3/4] Folders check kar raha hoon..."
mkdir -p "$DIR/data/signals"
echo "[OK] Folders ready!"
echo ""

echo "[4/4] Servers start ho rahe hain..."
echo ""
echo "============================================"
echo " Backend  : http://localhost:8000"
echo " Frontend : http://localhost:5173"
echo ""
echo " Dono terminals band mat karna!"
echo " Browser mein kholo: http://localhost:5173"
echo "============================================"
echo ""

# Start backend in new Terminal tab
osascript <<EOF
tell application "Terminal"
    activate
    do script "cd '$DIR/backend' && python3 -m uvicorn app.main:app --reload --port 8000"
end tell
EOF

# Wait then start frontend in another tab
sleep 3

osascript <<EOF
tell application "Terminal"
    activate
    do script "cd '$DIR/frontend' && npm run dev"
end tell
EOF

# Wait then open browser
sleep 5
open http://localhost:5173

echo "Setup complete! Browser khul gaya hoga."
echo "Dono terminal windows band mat karna."
