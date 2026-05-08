$ErrorActionPreference = "Stop"

$manifest = Join-Path $PSScriptRoot "SHA256SUMS.txt"

if (!(Test-Path -LiteralPath $manifest)) {
    throw "Manifest not found: $manifest"
}

$failed = $false

Get-Content -LiteralPath $manifest | ForEach-Object {
    $line = $_.Trim()
    if (-not $line) {
        return
    }

    $parts = $line -split "\s{2,}", 2
    if ($parts.Count -ne 2) {
        Write-Host "Malformed manifest entry: $line" -ForegroundColor Red
        $failed = $true
        return
    }

    $expectedHash = $parts[0].Trim().ToUpperInvariant()
    $path = $parts[1].Trim()

    if (!(Test-Path -LiteralPath $path)) {
        Write-Host "MISSING  $path" -ForegroundColor Red
        $failed = $true
        return
    }

    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToUpperInvariant()
    $item = Get-Item -LiteralPath $path
    $isReadOnly = [bool]($item.Attributes -band [IO.FileAttributes]::ReadOnly)

    if ($actualHash -ne $expectedHash) {
        Write-Host "CHANGED  $path" -ForegroundColor Red
        Write-Host "  expected: $expectedHash" -ForegroundColor DarkRed
        Write-Host "  actual:   $actualHash" -ForegroundColor DarkRed
        $failed = $true
        return
    }

    if (-not $isReadOnly) {
        Write-Host "OK*      $path (hash OK, but file is not read-only)" -ForegroundColor Yellow
        return
    }

    Write-Host "OK       $path" -ForegroundColor Green
}

if ($failed) {
    Write-Host ""
    Write-Host "Integrity check failed." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Integrity check passed." -ForegroundColor Green
