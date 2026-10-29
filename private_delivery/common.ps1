$ErrorActionPreference = 'Stop'
$env:PSModulePath = Join-Path $PSHOME 'Modules'
$script:PackageRoot = [IO.Path]::GetFullPath($PSScriptRoot)
if (!(Test-Path -LiteralPath (Join-Path $PackageRoot 'customer-package.json'))) { throw 'Not a Shiwen customer package.' }
$env:SHIWEN_CORE_DATA_DIR = Join-Path $PackageRoot 'data-core'
$env:SHIWEN_DATA_DIR = $env:SHIWEN_CORE_DATA_DIR
$env:SHIWEN_PROFILE = 'core'
$env:SHIWEN_PUBLIC = '0'
$env:PYTHONUTF8 = '1'
$env:PYTHONNOUSERSITE = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:UV_CACHE_DIR = Join-Path $PackageRoot '.runtime/cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $PackageRoot '.runtime/python'
$env:Path = (Join-Path $PackageRoot '.runtime/bin')+';'+$env:Path
function Run-Checked([string]$Exe,[string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw ('Command failed: '+[IO.Path]::GetFileName($Exe)) }
}
