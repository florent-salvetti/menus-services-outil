# Build portable Windows — Générateur de documents Les Menus Services.
# Lance : powershell -ExecutionPolicy Bypass -File build_portable.ps1
#
# 1) construit l'exe avec PyInstaller (--onedir via le .spec)
# 2) copie les DONNÉES à côté de l'exe (modeles/, tarifs.json, config.example.json)
# 3) copie tesseract/ et libreoffice/ s'ils sont présents (binaires embarqués)
# Résultat : dist\MenusServices\  = le dossier à copier sur le PC de Michaël.

$ErrorActionPreference = "Stop"
$racine = $PSScriptRoot
$dist = Join-Path $racine "dist\MenusServices"

Write-Host "== 1. PyInstaller ==" -ForegroundColor Cyan
pyinstaller --noconfirm MenusServices.spec

Write-Host "== 2. Copie des donnees a cote de l'exe ==" -ForegroundColor Cyan
Copy-Item (Join-Path $racine "modeles")            (Join-Path $dist "modeles") -Recurse -Force
Copy-Item (Join-Path $racine "assets")             (Join-Path $dist "assets") -Recurse -Force
Copy-Item (Join-Path $racine "tarifs.json")        $dist -Force
Copy-Item (Join-Path $racine "config.example.json") $dist -Force

Write-Host "== 3. Binaires embarques (si presents) ==" -ForegroundColor Cyan
foreach ($bin in @("tesseract", "libreoffice")) {
    $src = Join-Path $racine $bin
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $dist $bin) -Recurse -Force
        Write-Host "   $bin copie."
    } else {
        Write-Host "   $bin absent (a deposer manuellement dans le dossier livre)." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "OK -> $dist" -ForegroundColor Green
Write-Host "Rappel : creer config.json (copie de config.example.json) avec la vraie cle de licence." -ForegroundColor Yellow
