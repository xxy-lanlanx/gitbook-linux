#!/usr/bin/env pwsh
$ErrorActionPreference = "Stop"
$baseDir = "e:/doc/gitbook/gitbook-linux"
$files = Get-ChildItem -Path $baseDir -Recurse -Filter "*.md"

foreach ($file in $files) {
    $content = Get-Content $file.FullName -Raw
    $relativeDir = $file.DirectoryName.Replace($baseDir, "").TrimStart("\")
    $depth = 0
    if ($relativeDir -ne "") {
        $depth = ($relativeDir -split "\\").Count
    }
    
    $prefix = ""
    for ($i = 0; $i -lt $depth; $i++) {
        $prefix += "../"
    }
    if ($prefix -eq "") { $prefix = "./" }
    
    $matches = [regex]::Matches($content, 'https://pic\d+\.zhimg\.com[^\)\s\]\>\"]+')
    $replaced = $false
    foreach ($m in $matches) {
        $url = $m.Value.Trim()
        $fileName = [System.IO.Path]::GetFileName($url)
        $fileName = $fileName -replace '[<>\\|:\*?\"]', '_'
        $localPath = $prefix + "assets/images/" + $fileName
        $content = $content -replace [regex]::Escape($url), $localPath
        $replaced = $true
    }
    
    if ($replaced) {
        Set-Content -Path $file.FullName -Value $content -NoNewline
        Write-Host "Replaced: $($file.FullName)"
    }
}

Write-Host "Done."
