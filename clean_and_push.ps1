# Script to clean repository and push to GitHub
# Run this in PowerShell: .\clean_and_push.ps1

Write-Host "Step 1: Removing all files from Git cache..." -ForegroundColor Yellow
git rm -r --cached .

Write-Host "Step 2: Re-adding files (respecting .gitignore)..." -ForegroundColor Yellow
git add .

Write-Host "Step 3: Committing changes..." -ForegroundColor Yellow
git commit -m "Clean repo: Remove large files and update .gitignore"

Write-Host "Step 4: Checking repository size..." -ForegroundColor Yellow
$size = (git count-objects -vH | Select-String "size-pack").ToString()
Write-Host "Repository size: $size" -ForegroundColor Cyan

Write-Host "Step 5: Checking for large files still tracked..." -ForegroundColor Yellow
git ls-files | ForEach-Object {
    if (Test-Path $_) {
        $item = Get-Item $_ -ErrorAction SilentlyContinue
        if ($item -and $item.Length -gt 10MB) {
            Write-Host "Large file found: $($item.FullName) - $([math]::Round($item.Length/1MB, 2)) MB" -ForegroundColor Red
        }
    }
}

Write-Host "Step 6: Pushing to GitHub..." -ForegroundColor Yellow
git push -u origin main --force

Write-Host "Done!" -ForegroundColor Green



