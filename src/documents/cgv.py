"""Personnalisation des CGV jointes au dossier.

Les CGV restent un texte réglementaire joint tel quel (CLAUDE.md §4) : on ne
remplit QUE la zone de signature de la dernière page — « Nom », « Prénom » et
« Date » — en écrivant les valeurs à la place des lignes en underscores, sans
toucher au reste du document ni à la mise en page (révision client 11/06/2026).
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document

from src.chemins import RACINE

MODELE_CGV = RACINE / "modeles" / "CGV Les Menus Services Orange client.docx"

#: Une « ligne à remplir » de la trame : suite d'au moins 2 underscores.
_BLANC = re.compile(r"_{2,}")


def _remplir_blancs(paragraphe, valeurs: list[str]) -> None:
    """Remplace les suites d'underscores du paragraphe par `valeurs`, dans
    l'ordre. On réécrit le texte des runs existants → la mise en forme
    (police, taille) est conservée. Une valeur vide laisse le blanc en place.
    """
    it = iter(valeurs)

    def _sub(m: re.Match) -> str:
        v = next(it, None)
        return v if v else m.group(0)

    for run in paragraphe.runs:
        if "_" in run.text:
            run.text = _BLANC.sub(_sub, run.text)


def _morceaux_date(date_str: str) -> list[str]:
    """« 10/06/2026 » -> ["10", "06", "2026"] pour les 3 blancs de la ligne
    « Date : __ / __ / _____ ». Liste vide (blancs conservés) si la date
    saisie n'est pas au format JJ/MM/AAAA."""
    m = re.fullmatch(r"\s*(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{2,4})\s*", date_str or "")
    if not m:
        return []
    return [m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)]


def generer_cgv(
    nom: str,
    prenom: str,
    date_signature: str,
    sortie: Path,
    modele: Path = MODELE_CGV,
) -> Path:
    """Copie les CGV en remplissant Nom / Prénom / Date de la zone de signature."""
    doc = Document(str(modele))
    for p in doc.paragraphs:
        texte = p.text
        if "_" not in texte:
            continue
        if "Nom" in texte and "Prénom" in texte:
            _remplir_blancs(p, [nom.strip().upper(), prenom.strip()])
        elif texte.lstrip().startswith("Date"):
            _remplir_blancs(p, _morceaux_date(date_signature))
    sortie.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(sortie))
    return sortie
