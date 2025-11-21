# Copy version-controlled templates into the vault templates folder
Copy-Item -Recurse -Force "config/obsidian-templates/*" "knowledge/notes/_templates/"
Write-Output "Templates synced to knowledge/notes/_templates/"

