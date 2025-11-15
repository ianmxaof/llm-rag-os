$python = "C:\Users\ianmp\Miniconda3\envs\llmrag\python.exe"
$queryScript = Join-Path $PSScriptRoot "..\src\query_local.py"

if (-not (Test-Path $python)) {
    Write-Error "Python interpreter not found at $python."
    exit 1
}

if (-not (Test-Path $queryScript)) {
    Write-Error "query_local.py not found at $queryScript."
    exit 1
}

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Question
)

$joined = $Question -join " "
if (-not $joined) {
    & $python $queryScript
} else {
    $joined | & $python $queryScript
}

