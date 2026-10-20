$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    py -3.11 -m venv .venv
    & $taskPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw '依赖安装失败。' }
}
& $taskPython -X utf8 -m uvicorn app:app --host 127.0.0.1 --port 8765
