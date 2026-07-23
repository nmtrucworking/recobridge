$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DocsRoot = Join-Path $ProjectRoot "docs"
$ManifestPath = Join-Path $DocsRoot "manifest.json"
$ObsidianRoot = Join-Path $DocsRoot ".obsidian"
$Files = Get-ChildItem -LiteralPath $DocsRoot -Recurse -File |
    Where-Object { $_.FullName -ne $ManifestPath -and -not $_.FullName.StartsWith($ObsidianRoot) } |
    Sort-Object FullName

$Entries = foreach ($File in $Files) {
    $Relative = $File.FullName.Substring($DocsRoot.Length).TrimStart("\", "/").Replace("\", "/")
    @{
        path = $Relative
        size = $File.Length
        sha256 = (Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

@{
    project = "RecoBridge"
    version = "1.3.0"
    generated_at = (Get-Date).ToString("yyyy-MM-dd")
    tracked_file_count = $Entries.Count
    note = "manifest.json is intentionally excluded from its own checksum list"
    files = @($Entries)
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ManifestPath -Encoding utf8

Write-Host "Updated docs manifest with $($Entries.Count) files."
