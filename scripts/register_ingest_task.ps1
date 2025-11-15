param(
    [string]$TaskName = "LLM-RAG-Ingest",
    [string]$Schedule = "DAILY",
    [string]$StartTime = "02:00",
    [switch]$NoReset
)

$runScript = Join-Path $PSScriptRoot "run_ingest.ps1"
if (-not (Test-Path $runScript)) {
    Write-Error "run_ingest.ps1 not found at $runScript."
    exit 1
}

$escaped = $runScript.Replace('"', '""')
$arguments = "-ExecutionPolicy Bypass -File `"$escaped`""
if ($NoReset) {
    $arguments += " -NoReset"
}

SCHTASKS /Create `
    /TN $TaskName `
    /TR "powershell.exe $arguments" `
    /SC $Schedule `
    /ST $StartTime `
    /RL LIMITED `
    /F

Write-Host "Scheduled task '$TaskName' created. Adjust credentials/RunAs in Task Scheduler if needed."

