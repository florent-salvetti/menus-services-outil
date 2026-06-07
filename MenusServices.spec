# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller --onedir — Générateur de documents Les Menus Services.

NE bundle QUE le code + les libs (Qt, python-docx, pypdf, etc.) dans _internal/.
Les DONNÉES (modeles/, tarifs.json, config.json, tesseract/, dossiers/, donnees/)
NE sont PAS figées ici : elles vivent À CÔTÉ de l'exe (copiées par build_portable.ps1)
et sont résolues via src/chemins.py (RACINE = dossier de l'exe une fois packagé).

Build : pyinstaller MenusServices.spec   (sur Windows)
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Données internes de libs qui en ont besoin (modèle .docx par défaut de
# python-docx, ressources docxtpl). RIEN de nos données métier ici.
datas = collect_data_files("docx") + collect_data_files("docxtpl")

# Imports chargés paresseusement (dans des fonctions) -> on les force.
hiddenimports = (
    ["pytesseract", "PIL", "fitz", "requests", "pythoncom", "win32timezone"]
    + collect_submodules("win32com")
)

a = Analysis(
    ["src/ui/app.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MenusServices",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # application fenêtrée (pas de console)
    disable_windowed_traceback=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MenusServices",   # -> dist/MenusServices/
)
