param(
    [string]$ApiUrl = "http://localhost:8000",
    [string]$WebUrl = "http://localhost:3000"
)

$ErrorActionPreference = "Stop"
$Headers = @{ Authorization = "Bearer recobridge-demo-token" }
$Health = Invoke-RestMethod -Uri "$ApiUrl/v1/health/ready" -TimeoutSec 5
if ($Health.status -notin @("ok", "degraded")) { throw "API readiness failed" }

$Profiles = @("10002945", "10005456")
$Results = @()
foreach ($UserId in $Profiles) {
    $Body = @{
        user_id = $UserId
        session_id = "presentation-smoke"
        context = @{ page_type = "home"; device_type = "desktop" }
        top_k = 4
        strategy = "hybrid"
    } | ConvertTo-Json -Depth 4
    $Results += Invoke-RestMethod -Uri "$ApiUrl/v1/recommendations" -Method Post `
        -Headers $Headers -ContentType "application/json" -Body $Body -TimeoutSec 5
}

$First = @($Results[0].items | ForEach-Object product_id) -join ","
$Second = @($Results[1].items | ForEach-Object product_id) -join ","
if ($First -eq $Second) { throw "Release profiles returned identical top-N lists" }
if ($Results[0].strategy_used -ne "category_popular") { throw "Unexpected production strategy" }

$GuestBody = @{
    user_id = $null
    session_id = "presentation-guest"
    context = @{ page_type = "home"; device_type = "desktop" }
    top_k = 4
    strategy = "hybrid"
} | ConvertTo-Json -Depth 4
$Guest = Invoke-RestMethod -Uri "$ApiUrl/v1/recommendations" -Method Post `
    -Headers $Headers -ContentType "application/json" -Body $GuestBody -TimeoutSec 5
if ($Guest.strategy_used -ne "recent_popular" -or -not $Guest.degraded) {
    throw "Cold-start fallback contract failed"
}

$WebHealth = Invoke-RestMethod -Uri "$WebUrl/api/health" -TimeoutSec 5
Write-Host "PASS model=$($Results[0].model_version) strategy=$($Results[0].strategy_used)"
Write-Host "PASS profile A=$First"
Write-Host "PASS profile B=$Second"
Write-Host "PASS guest strategy=$($Guest.strategy_used)"
Write-Host "PASS web BFF status=$($WebHealth.status)"
