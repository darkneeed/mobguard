Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Get-EnvMap {
    param([string]$Path)

    $result = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#') -or -not $trimmed.Contains('=')) {
            continue
        }
        $parts = $trimmed.Split('=', 2)
        $result[$parts[0].Trim()] = $parts[1].Trim()
    }
    return $result
}

if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
    Write-Host '[INFO] Created .env from .env.example'
}

$envMap = Get-EnvMap '.env'
$missing = @()
foreach ($key in @('TG_MAIN_BOT_TOKEN', 'TG_ADMIN_BOT_TOKEN', 'TG_ADMIN_BOT_USERNAME', 'IPINFO_TOKEN')) {
    if (-not $envMap.ContainsKey($key)) {
        $missing += $key
    }
}
if (-not ($envMap.ContainsKey('REMNAWAVE_API_TOKEN') -or $envMap.ContainsKey('PANEL_TOKEN'))) {
    $missing += 'REMNAWAVE_API_TOKEN'
}
if ($missing.Count -gt 0) {
    throw "Missing required .env keys: $($missing -join ', ')"
}

New-Item -ItemType Directory -Force 'runtime', 'runtime\health' | Out-Null
if (-not (Test-Path -LiteralPath 'runtime\config.json')) {
    throw 'runtime/config.json is required'
}

Get-Command docker | Out-Null

docker compose build
docker compose run --rm --no-deps mobguard-api python -c "from api.app import app; print(app.title)"
Write-Host '[OK] Panel build and container smoke-check passed'
Write-Host '[INFO] Build does not start containers. Run: docker compose up -d'
