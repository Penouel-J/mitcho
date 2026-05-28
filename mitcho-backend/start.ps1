# MITCHÔ Backend — Script de démarrage rapide (PowerShell)
# Usage : .\start.ps1

Write-Host ""
Write-Host "======================================" -ForegroundColor Green
Write-Host "  MITCHÔ Backend — Démarrage          " -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host ""

$venvPath = ".\.venv"
$pythonExe = "$venvPath\Scripts\python.exe"
$uvicornExe = "$venvPath\Scripts\uvicorn.exe"

# Créer le venv si absent
if (-not (Test-Path $pythonExe)) {
    Write-Host "[1/3] Création de l'environnement virtuel Python..." -ForegroundColor Cyan
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Erreur : Python n'est pas installé ou non accessible." -ForegroundColor Red
        Write-Host "Téléchargez Python 3.11+ depuis https://python.org" -ForegroundColor Yellow
        exit 1
    }
}

# Installer les dépendances
Write-Host "[2/3] Installation des dépendances (peut prendre 2-5 min la première fois)..." -ForegroundColor Cyan
& $pythonExe -m pip install -q --upgrade pip
& $pythonExe -m pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "Erreur lors de l'installation des dépendances." -ForegroundColor Red
    exit 1
}

Write-Host "[3/3] Démarrage du serveur FastAPI..." -ForegroundColor Cyan
Write-Host ""
Write-Host "API disponible sur : http://localhost:8000" -ForegroundColor Green
Write-Host "Documentation      : http://localhost:8000/docs" -ForegroundColor Green
Write-Host "Arrêter            : Ctrl+C" -ForegroundColor Yellow
Write-Host ""

& $venvPath\Scripts\uvicorn.exe main:app --reload --port 8000 --host 0.0.0.0
