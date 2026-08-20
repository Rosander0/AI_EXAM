# SANKET Demo Runner — Single command PowerShell launch

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " Starting SANKET AI Exam Invigilation Assistant" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# Start backend server job
$serverProcess = Start-Process python -ArgumentList "-m uvicorn server.app:app --host 127.0.0.1 --port 8000" -PassThru

Write-Host "[INFO] Backend server running on http://127.0.0.1:8000 (PID: $($serverProcess.Id))" -ForegroundColor Green
Write-Host "[INFO] Opening Invigilator Dashboard in browser..." -ForegroundColor Green

Start-Sleep -Seconds 2
Start-Process "http://localhost:8000/"

Write-Host "[INFO] SANKET running. Close window or terminate process to exit." -ForegroundColor Yellow
$serverProcess.WaitForExit()
