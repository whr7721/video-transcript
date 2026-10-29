param([switch]$RemoveData,[switch]$StopOnly)
. (Join-Path $PSScriptRoot 'common.ps1')
$record=Join-Path $PackageRoot '.runtime/server.json'
if(Test-Path -LiteralPath $record){
    $server=Get-Content $record -Raw|ConvertFrom-Json
    $p=Get-CimInstance Win32_Process -Filter ('ProcessId='+[int]$server.pid)
    if($p){
        if(!$p.ExecutablePath -or !$p.ExecutablePath.StartsWith($PackageRoot+'\',[StringComparison]::OrdinalIgnoreCase) -or $p.CommandLine -notmatch 'uvicorn app_core:app'){throw 'Process identity changed; refusing to stop an unrelated process.'}
        # Windows venv python.exe may be a launcher with a managed-Python child.
        $snapshot=@(Get-CimInstance Win32_Process)
        $tree=New-Object 'System.Collections.Generic.List[object]'
        $tree.Add($p)
        for($i=0;$i -lt $tree.Count;$i++) {
            foreach($child in @($snapshot | Where-Object {$_.ParentProcessId -eq $tree[$i].ProcessId})) {
                if($child.ExecutablePath -and $child.ExecutablePath.Equals((Join-Path $env:SystemRoot 'System32/conhost.exe'),[StringComparison]::OrdinalIgnoreCase)){continue}
                if(!$child.ExecutablePath -or !$child.ExecutablePath.StartsWith($PackageRoot+'\',[StringComparison]::OrdinalIgnoreCase) -or $child.CommandLine -notmatch 'uvicorn app_core:app'){throw 'Unexpected service child process; refusing to stop it.'}
                $tree.Add($child)
            }
        }
        for($i=$tree.Count-1;$i -ge 0;$i--) {
            Stop-Process -Id $tree[$i].ProcessId -ErrorAction SilentlyContinue
            Wait-Process -Id $tree[$i].ProcessId -Timeout 15 -ErrorAction SilentlyContinue
        }
    }
}
if($StopOnly){
    if(Test-Path -LiteralPath $record){Remove-Item -LiteralPath $record -Force}
    Write-Host 'Service stopped. Documents and runtime are preserved.'
    exit 0
}
# Refuse active CLI processes; never kill a customer's in-progress transcription.
$active=Get-CimInstance Win32_Process | Where-Object {$_.ExecutablePath -and $_.ExecutablePath.StartsWith($PackageRoot+'\',[StringComparison]::OrdinalIgnoreCase)}
if($active){throw 'Close this package CLI before uninstalling.'}
$names=@('.venv','.runtime','models','__pycache__')
if($RemoveData){$names+='data-core'}
foreach($name in $names){
    $target=[IO.Path]::GetFullPath((Join-Path $PackageRoot $name))
    if(!$target.StartsWith($PackageRoot+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Unsafe uninstall target.'}
    if(Test-Path -LiteralPath $target){
        $linked=Get-Item -LiteralPath $target -Force
        if($linked.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Refusing linked uninstall target.'}
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}
Write-Host 'Uninstalled package-managed runtimes and models. Original source audio and other applications were not removed.'
if(!$RemoveData){Write-Host 'Your documents remain in data-core. Back up before using -RemoveData.'}
