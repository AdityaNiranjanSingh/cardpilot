Set-Location -Path $PSScriptRoot
Write-Host "Starting CardPilot" -ForegroundColor Cyan
if (!(Test-Path ".venv\Scripts\python.exe")) {
    py -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Start-Process "http://127.0.0.1:8000"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
