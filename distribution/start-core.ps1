$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
& "$PSScriptRoot\.venv\Scripts\python.exe" -m uvicorn app_core:app --host 127.0.0.1 --port 8766
exit $LASTEXITCODE
