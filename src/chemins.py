"""Résolution centralisée de la racine de l'application (dev ET packagé).

C'est LE point unique qui gère la portabilité PyInstaller : une fois packagé,
`__file__` pointe dans le bundle figé (_internal/), pas à côté de l'exe. On
résout donc la racine selon le contexte, et tous les modules s'y réfèrent via
`RACINE` (modeles/, tarifs.json, config.json, tesseract/, dossiers/, donnees/…
vivent À CÔTÉ de l'exe une fois packagé, dans la racine du projet en dev).
"""

from __future__ import annotations

import sys
from pathlib import Path


def _racine() -> Path:
    if getattr(sys, "frozen", False):           # exécutable PyInstaller
        return Path(sys.executable).resolve().parent   # dossier de l'exe (copiable)
    return Path(__file__).resolve().parent.parent       # racine du projet (dev)


RACINE = _racine()
