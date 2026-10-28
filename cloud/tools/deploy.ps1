param(
    [string]$ProjectName = 'shiwen-cloud-whr7721',
    [string]$SupabaseUrl,
    [string]$SupabaseAnonKey,
    [switch]$PrepareOnly
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Security/Microsoft.PowerShell.Security.psd1') -ErrorAction Stop
Set-Location (Split-Path -Parent $PSScriptRoot)
if ($ProjectName -notmatch '^[a-z][a-z0-9-]{2,48}$') { throw 'ProjectName must be a lowercase project slug.' }
function Run-Npm([string[]]$Arguments) {
    & npm.cmd @Arguments
    if ($LASTEXITCODE -ne 0) { throw ('Command failed: npm ' + ($Arguments -join ' ')) }
}
function Read-Secret([string]$Prompt) {
    $value = Read-Host $Prompt -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($value)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}
Run-Npm -Arguments @('ci','--no-fund')
Run-Npm -Arguments @('test')
Run-Npm -Arguments @('run','build')
if ($PrepareOnly) {
    Run-Npm -Arguments @('exec','wrangler','--','deploy','--dry-run','--outdir','.wrangler/dry-run')
    Write-Host 'Prepared frontend dist/ and Worker bundle .wrangler/dry-run/. No cloud resources changed.'
    return
}
if ($SupabaseUrl -notmatch '^https://[a-z0-9-]+\.supabase\.co$' -or [string]::IsNullOrWhiteSpace($SupabaseAnonKey)) {
    throw 'Provide SupabaseUrl and SupabaseAnonKey from a NEW project after applying schema.sql.'
}
Write-Host 'Use a free Cloudflare account. Complete wrangler login in another terminal if required.'
Run-Npm -Arguments @('exec','wrangler','--','whoami','--json')
$serviceKey = Read-Secret 'Supabase service_role key (hidden input; server only)'
$modelKey = Read-Secret 'SiliconFlow API key (hidden input; server only)'
if (!$serviceKey -or !$modelKey) { throw 'Both server-side keys are required.' }
# Verify the schema before publishing. Never print response data or credentials.
$probeHeaders = @{apikey=$serviceKey; Authorization=('Bearer '+$serviceKey)}
$null = Invoke-RestMethod -Uri ($SupabaseUrl+'/rest/v1/cloud_transcripts?select=id&limit=1') -Headers $probeHeaders -TimeoutSec 20
$origin = 'https://' + $ProjectName + '.pages.dev'
$config = Get-Content wrangler.jsonc -Raw | ConvertFrom-Json
$config.name = $ProjectName + '-api'
$config.main = '../../worker/index.ts'
$config.vars.WEB_ORIGIN = $origin
$config | Add-Member -NotePropertyName workers_dev -NotePropertyValue $false -Force
$config | Add-Member -NotePropertyName preview_urls -NotePropertyValue $false -Force
New-Item -ItemType Directory -Path '.wrangler/launch' -Force | Out-Null
$configPath = Join-Path (Get-Location) '.wrangler/launch/wrangler.json'
[IO.File]::WriteAllText($configPath,($config | ConvertTo-Json -Depth 10),[Text.UTF8Encoding]::new($false))
$hasher = [Security.Cryptography.SHA256]::Create()
try { $ipSecret = [BitConverter]::ToString($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes('shiwen-ip-v1:'+$serviceKey))).Replace('-','').ToLowerInvariant() }
finally { $hasher.Dispose() }
# Stable across redeployments with the same service key; do not reset per-IP counters each deploy.
$secrets = @{SUPABASE_URL=$SupabaseUrl;SUPABASE_ANON_KEY=$SupabaseAnonKey;SUPABASE_SERVICE_ROLE_KEY=$serviceKey;SILICONFLOW_API_KEY=$modelKey;IP_HASH_SECRET=$ipSecret}
try {
    # Secret values go only through stdin, never command arguments or tracked files.
    $secrets | ConvertTo-Json -Compress | & npm.cmd exec wrangler -- secret bulk --config $configPath
    if ($LASTEXITCODE -ne 0) { throw 'Secret upload failed. Check Cloudflare authentication.' }
    Run-Npm -Arguments @('exec','wrangler','--','deploy','--config',$configPath)
    # Same-origin API via Pages Service Binding, no public workers.dev dependency.
    $env:VITE_API_URL = ''
    Run-Npm -Arguments @('run','build')
    # Add exact production origins to the CSP; preview subdomains are deliberately not trusted by API CORS.
    $headers = Get-Content public/_headers -Raw
    $headers += "`n  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' $SupabaseUrl; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`n"
    [IO.File]::WriteAllText((Join-Path (Get-Location) 'dist/_headers'),$headers,[Text.UTF8Encoding]::new($false))
    # Listing is read-only; create only when this exact Pages project is absent.
    $projectOutput = & npm.cmd exec wrangler -- pages project list --json
    if ($LASTEXITCODE -ne 0) { throw 'Cannot list Pages projects.' }
    $projects = ($projectOutput -join "`n") | ConvertFrom-Json
    if (!($projects | Where-Object {$_.name -eq $ProjectName -or $_.'Project Name' -eq $ProjectName})) {
        # Explicit classic Pages creation avoids newer Wrangler delegating to a Worker.
        Run-Npm -Arguments @('exec','wrangler','--','pages','project','create',$ProjectName,'--production-branch','main','--force')
    }
    $pagesConfig = @{name=$ProjectName;pages_build_output_dir='../../dist';compatibility_date=$config.compatibility_date;services=@(@{binding='API';service=($ProjectName+'-api')})}
    $pagesDir = Join-Path (Get-Location) '.wrangler/pages'
    New-Item -ItemType Directory -Path $pagesDir -Force | Out-Null
    $pagesConfigPath = Join-Path $pagesDir 'wrangler.json'
    [IO.File]::WriteAllText($pagesConfigPath,($pagesConfig | ConvertTo-Json -Depth 10),[Text.UTF8Encoding]::new($false))
    Run-Npm -Arguments @('exec','wrangler','--','--cwd',$pagesDir,'pages','deploy','../../dist','--project-name',$ProjectName,'--branch','main')
    $health = Invoke-RestMethod -Uri ($origin+'/api/health') -TimeoutSec 20
    if (!$health.ok -or !$health.configured) { throw 'Published but health check failed; inspect Pages bindings.' }
    Write-Host ('Published: ' + $origin)
    Write-Host ('API: ' + $origin + '/api')
    Write-Host ('Next: Supabase Auth Site URL and Redirect URLs must include ' + $origin)
    Write-Host 'Verify two real accounts, a five-minute recording, share revocation, mobile Safari and actual billing before inviting users.'
} finally {
    $serviceKey=$null; $modelKey=$null; $ipSecret=$null; $secrets=$null; $probeHeaders=$null
    Remove-Item Env:VITE_API_URL -ErrorAction SilentlyContinue
}
