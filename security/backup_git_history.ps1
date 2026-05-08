$ErrorActionPreference = "Stop"

$root = "D:\gpt novel\voice"
$backupRoot = Join-Path $root "backups"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$dest = Join-Path $backupRoot "git_history_$stamp"

New-Item -ItemType Directory -Path $dest -Force | Out-Null

$repos = @(
    @{
        Name = "voice-root"
        Path = $root
    },
    @{
        Name = "CosyVoice"
        Path = Join-Path $root "CosyVoice"
    }
)

foreach ($repo in $repos) {
    $repoName = $repo.Name
    $repoPath = $repo.Path
    $bundlePath = Join-Path $dest "$repoName.bundle"
    $logPath = Join-Path $dest "$repoName.log"
    $statusPath = Join-Path $dest "$repoName.status.txt"

    git -C $repoPath bundle create $bundlePath --all
    git -C $repoPath log --oneline --decorate --graph --all | Set-Content -LiteralPath $logPath -Encoding UTF8
    git -C $repoPath status --short --branch | Set-Content -LiteralPath $statusPath -Encoding UTF8
}

$manifest = Join-Path $dest "SHA256SUMS.txt"
Get-ChildItem -LiteralPath $dest -File | ForEach-Object {
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash
    "$hash  $($_.Name)"
} | Set-Content -LiteralPath $manifest -Encoding UTF8

$zipPath = "$dest.zip"
Compress-Archive -LiteralPath $dest -DestinationPath $zipPath -CompressionLevel Optimal -Force
$zipHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath).Hash

Write-Host "Backup created:" -ForegroundColor Green
Write-Host "  $dest"
Write-Host "Archive:" -ForegroundColor Green
Write-Host "  $zipPath"
Write-Host "Archive SHA256:" -ForegroundColor Green
Write-Host "  $zipHash"
