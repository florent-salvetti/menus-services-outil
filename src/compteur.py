"""Compteur local de numéros de devis (auto-incrément PAR JOUR).

Format demandé par le client : « JJMMAAAA-N » (ex. 10062026-1 = 1er devis du
10/06/2026). Stocké dans donnees/compteur_devis.json :
  { "dernier_jour": { "10062026": 2 } }
- `numero_propose` retourne le PROCHAIN numéro sans le consommer (pré-remplissage UI).
- `enregistrer_numero` marque un numéro comme utilisé (après génération réussie).

Aucune donnée bénéficiaire ici — uniquement des compteurs. Les anciennes clés
(« dernier » par année) sont ignorées sans erreur.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from src.chemins import RACINE
_FICHIER = RACINE / "donnees" / "compteur_devis.json"


def _charger() -> dict:
    try:
        return json.loads(_FICHIER.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _sauver(data: dict) -> None:
    _FICHIER.parent.mkdir(parents=True, exist_ok=True)
    _FICHIER.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _dernier(jour: str, data: dict) -> int:
    return int(data.get("dernier_jour", {}).get(jour, 0))


def numero_propose(jour: date | None = None) -> str:
    """Prochain numéro proposé (ex. « 10062026-1 ») — NE consomme pas."""
    jour = jour or date.today()
    cle = jour.strftime("%d%m%Y")
    return f"{cle}-{_dernier(cle, _charger()) + 1}"


def enregistrer_numero(numero: str) -> None:
    """Marque `numero` (« JJMMAAAA-N ») comme utilisé (met à jour le compteur)."""
    m = re.match(r"(\d{8})-(\d+)$", numero.strip())
    if not m:
        return
    cle, n = m.group(1), int(m.group(2))
    data = _charger()
    data.setdefault("dernier_jour", {})
    if n > _dernier(cle, data):
        data["dernier_jour"][cle] = n
        _sauver(data)
