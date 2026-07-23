$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ProcessFile = Join-Path $ProjectRoot "apps\ml\artifacts\demo\processes.json"

if (-not (Test-Path -LiteralPath $ProcessFile -PathType Leaf)) {
    Write-Host "No demo process file found."
    exit 0
}

$DemoProcesses = Get-Content -LiteralPath $ProcessFile -Encoding utf8 | ConvertFrom-Json
$ProcessIds = @($DemoProcesses.api_pid, $DemoProcesses.web_pid)
foreach ($Url in @($DemoProcesses.api_url, $DemoProcesses.web_url)) {
    $Port = ([Uri]$Url).Port
    $Listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -ne $Listener) {
        $ProcessIds += $Listener.OwningProcess
    }
}
foreach ($ProcessId in ($ProcessIds | Sort-Object -Unique)) {
    $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($null -ne $Process) {
        Stop-Process -Id $ProcessId
    }
}
Write-Host "RecoBridge demo processes stopped."
