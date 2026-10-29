param([ValidateRange(1024,65535)][int]$Port=8785,[switch]$NoBrowser)
. (Join-Path $PSScriptRoot 'common.ps1')
Set-Location $PackageRoot
$python=Join-Path $PackageRoot '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'Please run install.cmd first.' }
$probe=New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback,$Port)
try {$probe.Start()} catch { throw 'Port is occupied. Stop the existing instance or choose another -Port.' } finally {$probe.Stop()}
$process=Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','app:app','--host','127.0.0.1','--port',"$Port") -WorkingDirectory $PackageRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $PackageRoot '.runtime/server.out.log') -RedirectStandardError (Join-Path $PackageRoot '.runtime/server.err.log')
@{pid=$process.Id;port=$Port}|ConvertTo-Json|Set-Content (Join-Path $PackageRoot '.runtime/server.json')
$ready=$false
for($i=0;$i -lt 40;$i++) {
    try {$health=Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 2;if($health.status -eq 'ok' -and $health.models_ready){$ready=$true;break}}catch{}
    if($process.HasExited){break};Start-Sleep -Milliseconds 500
}
if(!$ready){throw 'Server did not start; see .runtime/server.err.log.'}
$url="http://127.0.0.1:$Port/studio/"
if(!$NoBrowser){Start-Process $url}
Write-Host ('Ready: '+$url)
