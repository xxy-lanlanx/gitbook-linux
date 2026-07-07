#!/usr/bin/env pwsh
$ErrorActionPreference = "Stop"
$imgDir = "e:/doc/gitbook/gitbook-linux/assets/images"
$files = Get-ChildItem -Path "e:/doc/gitbook/gitbook-linux" -Recurse -Filter "*.md"
$urls = @()
foreach ($file in $files) {
    $content = Get-Content $file.FullName -Raw
    $matches = [regex]::Matches($content, 'https://pic\d+\.zhimg\.com[^\)\s\]\>\"]+')
    foreach ($m in $matches) {
        $urls += $m.Value.Trim()
    }
}
$uniqueUrls = $urls | Sort-Object -Unique
$uniqueUrls | Out-File -FilePath "$imgDir/urls.txt" -Encoding utf8
Write-Host "Total unique URLs: $($uniqueUrls.Count)"
