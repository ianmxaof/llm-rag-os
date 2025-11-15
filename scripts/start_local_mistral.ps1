param(
    [string]$ModelId = "mistral-7b-instruct-v0.2",
    [int]$Port = 1234
)

$lmsCli = "C:\Users\ianmp\AppData\Local\Programs\LM Studio\resources\app\.webpack\lms.exe"

if (-not (Test-Path $lmsCli)) {
    Write-Error "LM Studio CLI not found at $lmsCli. Update the path in start_local_mistral.ps1."
    exit 1
}

Write-Host "Starting LM Studio server on port $Port using model '$ModelId'..."
& $lmsCli load $ModelId --gpu off --context-length 4096 --identifier $ModelId --yes | Out-Null
& $lmsCli server start --port $Port

