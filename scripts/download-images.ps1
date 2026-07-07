#!/usr/bin/env pwsh
$ErrorActionPreference = "Continue"
$imgDir = "e:/doc/gitbook/gitbook-linux/assets/images"
$urls = Get-Content "$imgDir/urls.txt" -Encoding utf8
$failedUrls = @()
$successCount = 0

foreach ($url in $urls) {
    if ([string]::IsNullOrWhiteSpace($url)) { continue }
    $fileName = [System.IO.Path]::GetFileName($url)
    # Sanitize filename
    $fileName = $fileName -replace '[<>\|:\*\?\"]', '_'
    $destPath = Join-Path $imgDir $fileName
    if (Test-Path $destPath) {
        $successCount++
        continue
    }
    try {
        Invoke-WebRequest -Uri $url -OutFile $destPath -TimeoutSec 30 -ErrorAction Stop
        $successCount++
        Write-Host "OK: $fileName"
    } catch {
        $failedUrls += $url
        Write-Host "FAIL: $url"
    }
}

$failedUrls | Out-File -FilePath "$imgDir/failed.txt" -Encoding utf8
Write-Host "Downloaded: $successCount / $($urls.Count)"
Write-Host "Failed: $($failedUrls.Count)"
