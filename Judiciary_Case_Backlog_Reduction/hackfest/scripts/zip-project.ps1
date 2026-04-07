# Zips the entire hackfest project for backup / transfer.
# Run from repo root:  powershell -ExecutionPolicy Bypass -File .\scripts\zip-project.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$destDir = Split-Path -Parent $root
$name = "NyayaFlow_hackfest_{0:yyyyMMdd_HHmmss}" -f (Get-Date)
$zipPath = Join-Path $destDir "$name.zip"

if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path (Join-Path $root "*") -DestinationPath $zipPath -Force
Write-Host "Created: $zipPath"
