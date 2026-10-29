param([switch]$Offline,[string]$ModelDir)
. (Join-Path $PSScriptRoot 'common.ps1')
$ProgressPreference = 'SilentlyContinue'
Set-Location $PackageRoot
if (![Environment]::Is64BitOperatingSystem) { throw 'Windows x64 is required.' }
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$runtime = Join-Path $PackageRoot '.runtime'
New-Item -ItemType Directory -Path $runtime,(Join-Path $runtime 'bin'),(Join-Path $runtime 'downloads') -Force | Out-Null
$lock = Get-Content (Join-Path $PackageRoot 'runtime-lock.json') -Raw | ConvertFrom-Json
foreach ($name in @('uv','ffmpeg','deno')) {
    $spec=$lock.$name
    $archive=Join-Path $runtime ('downloads/'+$name+'.zip')
    if (!(Test-Path -LiteralPath $archive) -or (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $spec.sha256) {
        if ($Offline) { throw ('Offline runtime cache missing: '+$name) }
        Write-Host ('Downloading '+$name+' '+$spec.version)
        Invoke-WebRequest -UseBasicParsing -Uri $spec.url -OutFile ($archive+'.part')
        if ((Get-FileHash -LiteralPath ($archive+'.part') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $spec.sha256) { throw ('Checksum failed: '+$name) }
        Move-Item -LiteralPath ($archive+'.part') -Destination $archive -Force
    }
    $expanded=Join-Path $runtime ('expanded/'+$name)
    Expand-Archive -LiteralPath $archive -DestinationPath $expanded -Force
    $bins=if ($name -eq 'ffmpeg') {@('ffmpeg.exe','ffprobe.exe')} elseif ($name -eq 'uv') {@('uv.exe')} else {@('deno.exe')}
    foreach($bin in $bins) {
        $found=@(Get-ChildItem -LiteralPath $expanded -Filter $bin -Recurse -File)
        if ($found.Count -ne 1) { throw ('Runtime archive layout invalid: '+$bin) }
        Copy-Item -LiteralPath $found[0].FullName -Destination (Join-Path $runtime ('bin/'+$bin)) -Force
    }
}
$uv=Join-Path $runtime 'bin/uv.exe'
$offlineArgs=if($Offline){@('--offline')}else{@()}
Run-Checked $uv (@('python','install','3.11.14','--no-bin','--no-registry','--no-config')+$offlineArgs)
$python = Join-Path $env:UV_PYTHON_INSTALL_DIR 'cpython-3.11.14-windows-x86_64-none/python.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'Managed Python not found.' }
if (!(Test-Path -LiteralPath (Join-Path $PackageRoot '.venv/Scripts/python.exe'))) {
    Run-Checked $uv (@('venv','--python',$python,'--seed','.venv','--no-config')+$offlineArgs)
}
Run-Checked $uv (@('pip','install','--python',(Join-Path $PackageRoot '.venv/Scripts/python.exe'),'-r','requirements.txt','--no-config')+$offlineArgs)
$venv=Join-Path $PackageRoot '.venv/Scripts/python.exe'
$modelArgs=@('delivery_models.py')
if($ModelDir){$modelArgs+=@('--model-dir',$ModelDir)}
if($Offline){$modelArgs+='--offline'}
Run-Checked $venv $modelArgs
Run-Checked $venv @('delivery_check.py')
Set-Content -LiteralPath (Join-Path $runtime 'installed.txt') -Value 'shiwen-customer-v1' -Encoding ASCII
Write-Host 'Installed. Open start.cmd, then follow USER_GUIDE.html to configure your AI Key.'
