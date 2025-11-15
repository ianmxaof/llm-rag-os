$ErrorActionPreference = "Stop"

Write-Host "`n=== LLM-RAG Environment Setup ===`n"

# Step 1: Check Miniconda
$condaPath = "$env:USERPROFILE\Miniconda3\Scripts\conda.exe"
if (-Not (Test-Path $condaPath)) {
    Write-Host "Downloading Miniconda..."
    $installer = "$env:TEMP\Miniconda3-latest-Windows-x86_64.exe"
    Invoke-WebRequest -Uri "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe" -OutFile $installer
    Write-Host "Installing Miniconda silently..."
    Start-Process -Wait -FilePath $installer -ArgumentList "/S", "/D=$env:USERPROFILE\Miniconda3"
    Remove-Item $installer -Force
} else {
    Write-Host "Miniconda already installed."
}

# Step 2: Init Conda
& "$env:USERPROFILE\Miniconda3\Scripts\conda.exe" init powershell | Out-Null
$env:Path += ";$env:USERPROFILE\Miniconda3\Scripts"

# Step 3: Create Environment
Write-Host "`nCreating conda environment 'llmrag-env'..."
conda create -y -n llmrag-env python=3.11
conda activate llmrag-env

# Step 4: Install Dependencies
if (Test-Path "./requirements.txt") {
    Write-Host "Installing dependencies..."
    pip install -r requirements.txt
}

# Step 5: Create .env file
$envFile = ".env"
if (-Not (Test-Path $envFile) -or -not (Get-Content $envFile -ErrorAction SilentlyContinue)) {
    Write-Host "`nEnter your OpenAI API key (optional):"
    $apiKey = Read-Host "OPENAI_API_KEY"
    if ($apiKey) {
        "OPENAI_API_KEY=$apiKey" | Out-File $envFile
        "CHROMA_PATH=./chroma" | Out-File $envFile -Append
    }
}

# Step 6: Create sample data
$dataPath = "data"
if (-Not (Test-Path $dataPath)) {
    New-Item -ItemType Directory -Path $dataPath | Out-Null
    @"
# Introduction

This is a demo file showing how the ingestion pipeline works.
The assistant reads and embeds markdown files for retrieval.
"@ | Out-File "$dataPath\intro.md" -Encoding utf8

    @"
# Personal Goals

1. Automate environment setup.
2. Build local knowledge assistant.
3. Add incremental ingestion pipeline.
"@ | Out-File "$dataPath\goals.md" -Encoding utf8

    @"
# Workflow Guide

Use 'python src/ingest.py' to process documents.
Then run 'python src/query.py' to ask questions.
"@ | Out-File "$dataPath\workflow.md" -Encoding utf8
}

# Step 7: Run ingestion
Write-Host "`nRunning initial data ingestion..."
python src/ingest.py

Write-Host "`n✅ Setup complete. Use:"
Write-Host "conda activate llmrag-env"
Write-Host "python src/query.py"

