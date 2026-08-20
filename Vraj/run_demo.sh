#!/usr/bin/env bash
# SANKET Demo Runner — Single command launch
set -e

echo "========================================================"
echo " Starting SANKET AI Exam Invigilation Assistant"
echo "========================================================"

# Start backend server in background
uvicorn server.app:app --host 127.0.0.1 --port 8000 &
SERVER_PID=$!

echo "[INFO] Backend server running on http://127.0.0.1:8000 (PID: $SERVER_PID)"
echo "[INFO] Opening Invigilator Dashboard in browser..."

sleep 2

# Open browser
if which xdg-open > /dev/null; then
  xdg-open http://localhost:8000/
elif which open > /dev/null; then
  open http://localhost:8000/
fi

echo "[INFO] SANKET running. Press CTRL+C to terminate."
wait $SERVER_PID
