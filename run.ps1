# Start the SPHEREx Time Explorer and open it in the default browser.
Set-Location $PSScriptRoot
Start-Process "http://localhost:8000"
python -m uvicorn server.app:app --port 8000
