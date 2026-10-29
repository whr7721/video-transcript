param([string]$TargetDir = (Join-Path $env:USERPROFILE '.agents\skills'))
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'skills\shiwen'
$destination = Join-Path $TargetDir 'shiwen'
New-Item -ItemType Directory -Force -Path $destination | Out-Null
Copy-Item -LiteralPath (Join-Path $source 'SKILL.md') -Destination $destination -Force
Copy-Item -LiteralPath (Join-Path $source 'agents') -Destination $destination -Recurse -Force
Write-Output "Installed Shiwen skill: $destination"
Write-Output 'Restart your agent session to discover the skill. Shiwen must already be installed.'
