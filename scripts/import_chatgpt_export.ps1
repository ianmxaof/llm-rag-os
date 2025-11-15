param(
    [string]$ExportZip,
    [string]$ExportFolder = "C:\Users\ianmp\Downloads",
    [string]$DestinationRoot = "C:\Powercore-repo-main\llm-rag\knowledge\chatgpt"
)

function Get-LatestExport {
    param([string]$Folder)
    Get-ChildItem -Path $Folder -Filter "ChatGPT_*.*.zip" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
}

if (-not $ExportZip) {
    $latest = Get-LatestExport -Folder $ExportFolder
    if (-not $latest) {
        Write-Error "No ChatGPT export zip found in $ExportFolder"
        exit 1
    }
    $ExportZip = $latest.FullName
}

if (-not (Test-Path $ExportZip)) {
    Write-Error "Export file not found: $ExportZip"
    exit 1
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = Join-Path $DestinationRoot $timestamp
New-Item -ItemType Directory -Path $dest -Force | Out-Null

Write-Host "Extracting $ExportZip to $dest ..."
Expand-Archive -LiteralPath $ExportZip -DestinationPath $dest -Force

Write-Host "Done. Imported ChatGPT export to $dest"

