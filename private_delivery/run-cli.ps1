. (Join-Path $PSScriptRoot 'common.ps1')
Set-Location $PackageRoot
& (Join-Path $PackageRoot '.venv/Scripts/python.exe') -X utf8 (Join-Path $PackageRoot 'shiwen.py') @args
exit $LASTEXITCODE
