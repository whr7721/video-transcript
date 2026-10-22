param([ValidateRange(1024,65535)][int]$Port = 8766)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = "$PSScriptRoot\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    Write-Host 'Missing .venv. Follow README to install Python 3.11 and dependencies.'
    exit 1
}
& $python check_core.py --port $Port
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Open http://127.0.0.1:$Port/studio/ . Press Ctrl+C to stop."
& $python -m uvicorn app_core:app --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
