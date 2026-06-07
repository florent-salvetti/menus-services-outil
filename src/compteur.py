"""Compteur local de numéros de devis (auto-incrément par année).

Stocké dans donnees/compteur_devis.json : { "dernier": { "2026": 3 } }.
- `numero_propose` retourne le PROCHAIN numéro sans le consommer (pré-remplissage UI).
- `enregistrer_numero` marque un numéro comme utilisé (après génération réussie).

Aucune donnée bénéficiaire ici — uniquement des compteurs.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
_FICHIER = RACINE / "donnees" / "compteur_devis.json"


def _charger() -> dict:
    try:
        return json.loads(_FICHIER.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"dernier": {}}


def _sauver(data: dict) -> None:
    _FICHIER.parent.mkdir(parents=True, exist_ok=True)
    _FICHIER.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _dernier(annee: int, data: dict) -> int:
    return int(data.get("dernier", {}).get(str(annee), 0))


def numero_propose(annee: int | None = None) -> str:
    """Prochain numéro proposé (ex. « 2026-0004 ») — NE consomme pas."""
    annee = annee or date.today().year
    return f"{annee}-{_dernier(annee, _charger()) + 1:04d}"


def enregistrer_numero(numero: str) -> None:
    """Marque `numero` (« AAAA-NNNN ») comme utilisé (met à jour le compteur)."""
    m = re.match(r"(\d{4})-(\d+)", numero.strip())
    if not m:
        return
    annee, n = int(m.group(1)), int(m.group(2))
    data = _charger()
    data.setdefault("dernier", {})
    if n > _dernier(annee, data):
        data["dernier"][str(annee)] = n
        _sauver(data)
