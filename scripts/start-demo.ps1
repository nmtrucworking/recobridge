param(
    [int]$ApiPort = 8000,
    [int]$WebPort = 3000
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ProductionAlias = Join-Path $ProjectRoot "apps\ml\artifacts\models\release\production.json"
$WebRoot = Join-Path $ProjectRoot "apps\web"
$VinextCli = Join-Path $WebRoot "node_modules\vinext\dist\cli.js"
$RuntimeRoot = Join-Path $ProjectRoot "apps\ml\artifacts\demo"

foreach ($RequiredPath in @($PythonPath, $ProductionAlias, $VinextCli)) {
    if (-not (Test-Path -LiteralPath $RequiredPath -PathType Leaf)) {
        throw "Missing demo dependency: $RequiredPath"
    }
}

New-Item -ItemType Directory -Path $RuntimeRoot -Force | Out-Null
$env:RECOBRIDGE_API_TOKEN = "recobridge-demo-token"
$env:RECOBRIDGE_MODEL_BUNDLE_PATH = $ProductionAlias
$env:RECOBRIDGE_DATABASE_URL = "memory://"
$env:RECOMMENDATION_API_URL = "http://localhost:$ApiPort"
$env:RECOMMENDATION_API_TOKEN = "recobridge-demo-token"
@"
RECOMMENDATION_API_URL=http://127.0.0.1:$ApiPort
RECOMMENDATION_API_TOKEN=recobridge-demo-token
"@ | Set-Content -LiteralPath (Join-Path $WebRoot ".env.local") -Encoding utf8

$ApiLog = Join-Path $RuntimeRoot "api.out.log"
$ApiErrorLog = Join-Path $RuntimeRoot "api.err.log"
$WebLog = Join-Path $RuntimeRoot "web.out.log"
$WebErrorLog = Join-Path $RuntimeRoot "web.err.log"
$ApiProcess = Start-Process -FilePath $PythonPath `
    -ArgumentList @("-m", "uvicorn", "recobridge_api.app:app", "--app-dir", "apps/api", "--port", $ApiPort) `
    -WorkingDirectory $ProjectRoot -RedirectStandardOutput $ApiLog -RedirectStandardError $ApiErrorLog `
    -WindowStyle Hidden -PassThru
$WebProcess = Start-Process -FilePath "node.exe" `
    -ArgumentList @($VinextCli, "dev", "--port", $WebPort) `
    -WorkingDirectory $WebRoot -RedirectStandardOutput $WebLog -RedirectStandardError $WebErrorLog `
    -WindowStyle Hidden -PassThru

@{
    api_pid = $ApiProcess.Id
    web_pid = $WebProcess.Id
    api_url = "http://localhost:$ApiPort"
    web_url = "http://localhost:$WebPort"
    production_alias = $ProductionAlias
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $RuntimeRoot "processes.json") -Encoding utf8

$Ready = $false
for ($Attempt = 0; $Attempt -lt 30; $Attempt++) {
    try {
        $Health = Invoke-RestMethod -Uri "http://localhost:$ApiPort/v1/health/ready" -TimeoutSec 2
        if ($Health.status -in @("ok", "degraded")) {
            $Ready = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $Ready) {
    throw "Recommendation API did not become ready; inspect $ApiLog"
}

$WebReady = $false
for ($Attempt = 0; $Attempt -lt 30; $Attempt++) {
    try {
        $WebHealth = Invoke-RestMethod -Uri "http://localhost:$WebPort/api/health" -TimeoutSec 2
        if ($WebHealth.status -in @("ok", "degraded")) {
            $WebReady = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $WebReady) {
    throw "Web BFF did not become ready; inspect $WebLog and $WebErrorLog"
}

$ApiOwner = (Get-NetTCPConnection -LocalPort $ApiPort -State Listen | Select-Object -First 1).OwningProcess
$WebOwner = (Get-NetTCPConnection -LocalPort $WebPort -State Listen | Select-Object -First 1).OwningProcess
@{
    api_pid = $ApiOwner
    web_pid = $WebOwner
    api_url = "http://localhost:$ApiPort"
    web_url = "http://localhost:$WebPort"
    production_alias = $ProductionAlias
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $RuntimeRoot "processes.json") -Encoding utf8

Write-Host "RecoBridge demo is ready"
Write-Host "Web: http://localhost:$WebPort"
Write-Host "API docs: http://localhost:$ApiPort/docs"
Write-Host "Run scripts\smoke-demo.ps1 to verify the live flow."
