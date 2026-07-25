# setup_venv.ps1
# Dieses Skript muss im Stammverzeichnis des Projekts liegen.
#
# Aufruf, damit die virtuelle Umgebung anschließend aktiviert bleibt:
# . .\setup_venv.ps1

$ErrorActionPreference = "Stop"

# Projektverzeichnis entspricht dem Verzeichnis dieses Skripts
$ProjectDirectory = $PSScriptRoot

if (-not $ProjectDirectory) {
    $ProjectDirectory = (Get-Location).Path
}

Set-Location $ProjectDirectory

Write-Host ""
Write-Host "Projektverzeichnis:" -ForegroundColor Cyan
Write-Host "  $ProjectDirectory"
Write-Host ""

# Unterstützte Standardnamen für virtuelle Umgebungen
$VenvCandidates = @(
    ".venv",
    "venv",
    "env"
)

$VenvDirectory = $null

foreach ($Candidate in $VenvCandidates) {
    $CandidatePath = Join-Path $ProjectDirectory $Candidate
    $ActivateScript = Join-Path $CandidatePath "Scripts\Activate.ps1"

    if (Test-Path $ActivateScript) {
        $VenvDirectory = $CandidatePath
        break
    }
}

if (-not $VenvDirectory) {
    Write-Host "Keine virtuelle Python-Umgebung gefunden." -ForegroundColor Red
    Write-Host ""
    Write-Host "Erwartet wurde einer dieser Ordner:"
    Write-Host "  .venv"
    Write-Host "  venv"
    Write-Host "  env"
    Write-Host ""
    Write-Host "Eine neue Umgebung kann beispielsweise so erstellt werden:"
    Write-Host "  python -m venv .venv" -ForegroundColor Yellow

    throw "Virtuelle Umgebung nicht gefunden."
}

$ActivateScript = Join-Path $VenvDirectory "Scripts\Activate.ps1"
$RequirementsFile = Join-Path $ProjectDirectory "requirements.txt"

Write-Host "Virtuelle Umgebung gefunden:" -ForegroundColor Green
Write-Host "  $VenvDirectory"
Write-Host ""

Write-Host "Aktiviere virtuelle Umgebung ..." -ForegroundColor Cyan
& $ActivateScript

if (-not $env:VIRTUAL_ENV) {
    throw "Die virtuelle Umgebung konnte nicht aktiviert werden."
}

Write-Host "Aktivierte Umgebung:" -ForegroundColor Green
Write-Host "  $env:VIRTUAL_ENV"
Write-Host ""

# Pip Update
Write-Host "Aktualisiere pip, setuptools und wheel ..." -ForegroundColor Cyan
python -m pip install --upgrade pip setuptools wheel

if ($LASTEXITCODE -ne 0) {
    throw "Die Aktualisierung von pip, setuptools oder wheel ist fehlgeschlagen."
}

if (Test-Path $RequirementsFile) {
    Write-Host ""
    Write-Host "Installiere und aktualisiere requirements.txt ..." -ForegroundColor Cyan

    python -m pip install --upgrade --requirement $RequirementsFile

    if ($LASTEXITCODE -ne 0) {
        throw "Die Installation der requirements.txt ist fehlgeschlagen."
    }
}
else {
    Write-Host ""
    Write-Host "Keine requirements.txt gefunden:" -ForegroundColor Yellow
    Write-Host "  $RequirementsFile"
}

Write-Host ""
Write-Host "Fertig." -ForegroundColor Green
Write-Host "Python:" -ForegroundColor Cyan
python --version

Write-Host "pip:" -ForegroundColor Cyan
python -m pip --version

Write-Host ""
Write-Host "Die virtuelle Umgebung ist aktiviert." -ForegroundColor Green