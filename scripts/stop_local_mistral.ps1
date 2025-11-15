$lmsCli = "C:\Users\ianmp\AppData\Local\Programs\LM Studio\resources\app\.webpack\lms.exe"

if (-not (Test-Path $lmsCli)) {
    Write-Error "LM Studio CLI not found at $lmsCli. Update the path in stop_local_mistral.ps1."
    exit 1
}

Write-Host "Stopping LM Studio server..."
& $lmsCli server stop
Write-Host "Done."

