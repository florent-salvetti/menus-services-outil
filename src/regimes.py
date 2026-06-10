"""Liste des régimes particuliers — donnée éditable (regimes.json).

Même philosophie que la grille tarifaire (CLAUDE.md §5) : la liste n'est pas
codée en dur, elle vit dans un fichier de données à côté de l'exécutable,
modifiable par l'utilisateur (éditeur intégré) ou à la main.

Le régime n'a AUCUNE incidence tarifaire : c'est un libellé reporté au bout du
nom de la prestation sur le devis et les conditions particulières.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.chemins import RACINE

FICHIER = RACINE / "regimes.json"

#: Liste historique (CLAUDE.md §8) — utilisée si regimes.json manque ou est
#: illisible : l'app doit toujours démarrer, même sans le fichier.
REGIMES_DEFAUT = ["diabétique", "sans sel", "mixé"]


def _nettoyer(liste) -> list[str]:
    """Libellés épurés : chaînes non vides, sans doublons (ordre conservé)."""
    vus: set[str] = set()
    propres: list[str] = []
    for r in liste:
        if not isinstance(r, str):
            continue
        r = r.strip()
        if r and r.lower() not in vus:
            vus.add(r.lower())
            propres.append(r)
    return propres


def charger_regimes(chemin: str | Path = FICHIER) -> list[str]:
    """Lit regimes.json ; liste par défaut si absent ou invalide."""
    try:
        data = json.loads(Path(chemin).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return list(REGIMES_DEFAUT)
    if not isinstance(data, list):
        return list(REGIMES_DEFAUT)
    propres = _nettoyer(data)
    return propres if propres else list(REGIMES_DEFAUT)


def enregistrer_regimes(liste: list[str], chemin: str | Path = FICHIER) -> list[str]:
    """Valide et écrit la liste ; retourne la liste épurée réellement écrite.

    Garde-fous (mêmes principes que l'éditeur de tarifs) :
    - liste vide ou sans libellé valide → ValueError (rien n'est écrit) ;
    - sauvegarde de l'ancien fichier en regimes.json.bak avant écriture.
    """
    propres = _nettoyer(liste)
    if not propres:
        raise ValueError("La liste des régimes ne peut pas être vide.")

    chemin = Path(chemin)
    if chemin.exists():
        bak = chemin.with_suffix(chemin.suffix + ".bak")
        bak.write_text(chemin.read_text(encoding="utf-8-sig"), encoding="utf-8")

    chemin.write_text(
        json.dumps(propres, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return propres
