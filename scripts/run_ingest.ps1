param(
    [switch]$NoReset,
    [string[]]$ExtraSource,
    [switch]$Fast,
    [switch]$Parallel
)

$env:PATH = "C:\Users\ianmp\Miniconda3\envs\llmrag;C:\Users\ianmp\Miniconda3\envs\llmrag\Scripts;$env:PATH"
$python = "C:\Users\ianmp\Miniconda3\envs\llmrag\python.exe"
$ingestScript = Join-Path $PSScriptRoot "ingest.py"

if (-not (Test-Path $python)) {
    Write-Error "Python interpreter not found at $python. Update run_ingest.ps1."
    exit 1
}

if (-not (Test-Path $ingestScript)) {
    Write-Error "Could not locate ingest.py in $PSScriptRoot."
    exit 1
}

$argsList = @($ingestScript)
if ($NoReset) { $argsList += "--no-reset" }
if ($Fast) { $argsList += "--fast" }
if ($Parallel) { $argsList += "--parallel" }
foreach ($src in $ExtraSource) {
    if ($src) { $argsList += @("--src", $src) }
}

& $python @argsList

