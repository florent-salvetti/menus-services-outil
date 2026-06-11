# Build portable Windows — Générateur de documents Les Menus Services.
# Lance : powershell -ExecutionPolicy Bypass -File build_portable.ps1
# Option : -SansZip pour sauter l'archive de livraison (itérations locales).
#
# 1) construit l'exe avec PyInstaller (--onedir via le .spec)
# 2) copie les DONNÉES à côté de l'exe (modeles/, tarifs.json, config.example.json)
# 3) copie libreoffice/ s'il est présent (binaire embarqué optionnel).
#    tesseract/ n'est PLUS livré : l'OCR du RIB est débranché de l'UI depuis
#    la révision client du 10/06/2026 (aucune coordonnée bancaire saisie).
# 4) compresse le tout en dist\MenusServices.zip (livraison), SANS les fichiers
#    de dev (config.json, licences.dev.json) ni les artefacts locaux
# Résultat : dist\MenusServices\  = le dossier à copier sur le PC de Michaël,
#            dist\MenusServices.zip = l'archive à envoyer.

param([switch]$SansZip)

$ErrorActionPreference = "Stop"
$racine = $PSScriptRoot
$dist = Join-Path $racine "dist\MenusServices"

Write-Host "== 1. PyInstaller ==" -ForegroundColor Cyan
pyinstaller --noconfirm MenusServices.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller a echoue (code $LASTEXITCODE) - build interrompu, rien n'est copie ni zippe."
}

Write-Host "== 2. Copie des donnees a cote de l'exe ==" -ForegroundColor Cyan
Copy-Item (Join-Path $racine "modeles")            (Join-Path $dist "modeles") -Recurse -Force
# Les copies-templates balisees sont des caches REGENERES par l'app : une
# version perimee embarquee ferait generer les documents avec d'anciennes
# trames (l'app ne reconstruit que si le fichier manque).
Remove-Item (Join-Path $dist "modeles\_template_*.docx") -Force -ErrorAction SilentlyContinue
Copy-Item (Join-Path $racine "assets")             (Join-Path $dist "assets") -Recurse -Force
Copy-Item (Join-Path $racine "tarifs.json")        $dist -Force
Copy-Item (Join-Path $racine "regimes.json")       $dist -Force
Copy-Item (Join-Path $racine "config.example.json") $dist -Force

Write-Host "== 3. Binaires embarques (si presents) ==" -ForegroundColor Cyan
foreach ($bin in @("libreoffice")) {
    $src = Join-Path $racine $bin
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $dist $bin) -Recurse -Force
        Write-Host "   $bin copie."
    } else {
        Write-Host "   $bin absent (a deposer manuellement dans le dossier livre)." -ForegroundColor Yellow
    }
}

if ($SansZip) {
    Write-Host "== 4. Archive de livraison : SAUTEE (-SansZip) ==" -ForegroundColor Yellow
    Write-Host "   ATTENTION : dist\MenusServices.zip (s'il existe) date d'un build precedent." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "OK -> $dist" -ForegroundColor Green
    exit 0
}

Write-Host "== 4. Archive de livraison (dist\MenusServices.zip) ==" -ForegroundColor Cyan
# Copie de travail SANS les fichiers de dev ni les artefacts locaux : le zip
# livre ne doit contenir ni cle de licence, ni licences de dev, ni dossiers
# beneficiaires, ni compteurs/caches generes par des tests locaux.
$staging = Join-Path $env:TEMP "MenusServices_zip\MenusServices"
if (Test-Path (Split-Path $staging)) { Remove-Item (Split-Path $staging) -Recurse -Force }
New-Item -ItemType Directory -Force $staging | Out-Null
Copy-Item (Join-Path $dist "*") $staging -Recurse -Force
foreach ($exclu in @("config.json", "licences.dev.json", "dossiers", "donnees")) {
    Remove-Item (Join-Path $staging $exclu) -Recurse -Force -ErrorAction SilentlyContinue
}
Remove-Item (Join-Path $staging "modeles\_template_*.docx") -Force -ErrorAction SilentlyContinue
$zip = Join-Path $racine "dist\MenusServices.zip"
Remove-Item $zip -Force -ErrorAction SilentlyContinue
Compress-Archive -Path $staging -DestinationPath $zip -CompressionLevel Optimal
Remove-Item (Split-Path $staging) -Recurse -Force
Write-Host ("   {0:N1} Mo" -f ((Get-Item $zip).Length / 1MB))

Write-Host ""
Write-Host "OK -> $dist" -ForegroundColor Green
Write-Host "Archive  -> $zip" -ForegroundColor Green
Write-Host "Rappel : creer config.json (copie de config.example.json) avec la vraie cle de licence." -ForegroundColor Yellow
