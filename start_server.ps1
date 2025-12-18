# Start the Legal Assistant API server with ffmpeg available
# This script ensures ffmpeg is in PATH for audio transcription

Write-Host "Legal Assistant API Server Startup" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan

# Refresh PATH from registry to include ffmpeg
$machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
$userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$machinePath;$userPath"

# Verify ffmpeg is available
$ffmpegPath = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ffmpegPath) {
    Write-Host "ffmpeg found at: $($ffmpegPath.Source)" -ForegroundColor Green
} else {
    Write-Host "WARNING: ffmpeg not found in PATH" -ForegroundColor Yellow
    Write-Host "Audio transcription will not work." -ForegroundColor Yellow
    Write-Host "Install with: winget install ffmpeg" -ForegroundColor Yellow
    Write-Host "Then restart this script." -ForegroundColor Yellow
}

# Start the server
Write-Host ""
Write-Host "Starting FastAPI server..." -ForegroundColor Cyan
Write-Host "API will be available at: http://localhost:8000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

& .\.venv\Scripts\python.exe -m uvicorn api_server:app --reload --host 0.0.0.0 --port 8000
