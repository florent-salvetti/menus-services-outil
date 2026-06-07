"""Vérification de licence en ligne — kill switch (CLAUDE.md §15).

Au démarrage, l'app lit sa clé dans config.json et consulte un licences.json
hébergé sur un dépôt GitHub que le prestataire contrôle. Principe :

- Réponse du serveur reçue => décision DÉFINITIVE (actif / échéance / clé) :
  on autorise (et on mémorise la date de vérif réussie) ou on bloque tout de
  suite. La tolérance hors-ligne NE s'applique JAMAIS dans ce cas.
- Pas de réseau (timeout, URL injoignable, JSON illisible) => tolérance
  hors-ligne de N jours depuis la dernière vérif réussie ; au-delà, blocage.
- Config absente / clé ou URL manquante => blocage STRICT (un kill switch
  contournable en vidant config.json ne vaut rien).

Aucune donnée bénéficiaire n'est envoyée : lecture seule du fichier de statut.
Le `lecteur` est injectable (tests + URL locale pour le dev), `aujourdhui` et
`etat_path` aussi (tests déterministes).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Optional

from src.chemins import RACINE
CONFIG = RACINE / "config.json"
ETAT = RACINE / "donnees" / "licence_etat.json"
TIMEOUT = 5  # secondes


@dataclass
class ResultatLicence:
    autorise: bool
    message: str
    mode: str  # "en-ligne" | "hors-ligne" | "bloque"


# --------------------------------------------------------------------------- #
# Lecture config / état local
# --------------------------------------------------------------------------- #
def charger_config(path: Path = CONFIG) -> dict:
    """Charge config.json ; dict vide si absent/illisible (=> blocage strict).

    Lecture en utf-8-sig : tolère un BOM (fréquent si le fichier est édité sous
    Windows avec Notepad/PowerShell), sinon json.loads échouerait sur le BOM.
    """
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _lire_derniere_verif(etat_path: Path) -> Optional[date]:
    try:
        data = json.loads(Path(etat_path).read_text(encoding="utf-8-sig"))
        return date.fromisoformat(data["derniere_verif_reussie"])
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError, OSError):
        return None


def _enregistrer_verif(etat_path: Path, jour: date) -> None:
    try:
        Path(etat_path).parent.mkdir(parents=True, exist_ok=True)
        Path(etat_path).write_text(
            json.dumps({"derniere_verif_reussie": jour.isoformat()}, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass  # non bloquant : on a déjà autorisé


# --------------------------------------------------------------------------- #
# Lecteur par défaut : URL http(s) OU chemin local (dev)
# --------------------------------------------------------------------------- #
def _lecteur_defaut(url: str) -> str:
    """Retourne le texte du fichier de statut. http(s) -> réseau ; sinon local."""
    if url.lower().startswith(("http://", "https://")):
        import requests  # import paresseux : inutile pour un chemin local

        rep = requests.get(
            url, timeout=TIMEOUT, headers={"Cache-Control": "no-cache"}
        )
        rep.raise_for_status()
        return rep.text
    # Chemin local (dev) : résolu depuis la racine du projet si relatif.
    chemin = Path(url)
    if not chemin.is_absolute():
        chemin = RACINE / chemin
    return chemin.read_text(encoding="utf-8-sig")


def _parse_date(valeur) -> Optional[date]:
    try:
        return date.fromisoformat(valeur)
    except (TypeError, ValueError):
        return None


def _contact() -> str:
    return "Contactez votre prestataire."


# --------------------------------------------------------------------------- #
# Vérification
# --------------------------------------------------------------------------- #
def verifier(
    config: dict,
    lecteur: Optional[Callable[[str], str]] = None,
    aujourdhui: Optional[date] = None,
    etat_path: Optional[Path] = None,
) -> ResultatLicence:
    """Vérifie la licence et retourne l'autorisation de démarrage."""
    lecteur = lecteur or _lecteur_defaut
    aujourdhui = aujourdhui or date.today()
    etat_path = etat_path or ETAT

    lic = (config or {}).get("licence") or {}
    cle = str(lic.get("cle", "")).strip()
    url = str(lic.get("url_statut", "")).strip()
    tolerance = int(lic.get("tolerance_hors_ligne_jours", 5))

    # Config inexploitable -> blocage strict (jamais de tolérance ici).
    if not cle or not url:
        return ResultatLicence(
            False,
            "Licence non configurée (config.json absent ou incomplet). " + _contact(),
            "bloque",
        )

    # 1) Tentative de contact du serveur de statut.
    try:
        data = json.loads(lecteur(url))
    except Exception:  # noqa: BLE001 — réseau/parse : on passe en hors-ligne
        return _hors_ligne(cle, tolerance, aujourdhui, etat_path)

    # 2) Réponse reçue = décision DÉFINITIVE.
    entree = data.get(cle) if isinstance(data, dict) else None
    if entree is None:
        return ResultatLicence(
            False, f"Licence « {cle} » inconnue ou révoquée. " + _contact(), "bloque"
        )
    if not entree.get("actif", False):
        return ResultatLicence(
            False, f"Licence « {cle} » désactivée. " + _contact(), "bloque"
        )
    echeance = _parse_date(entree.get("echeance"))
    if echeance is None:
        return ResultatLicence(
            False, f"Licence « {cle} » : échéance invalide. " + _contact(), "bloque"
        )
    if echeance < aujourdhui:
        return ResultatLicence(
            False,
            f"Licence « {cle} » expirée (échéance {echeance.isoformat()}). " + _contact(),
            "bloque",
        )

    # Tout est bon -> on mémorise la date de vérif réussie.
    _enregistrer_verif(etat_path, aujourdhui)
    return ResultatLicence(True, "Licence valide.", "en-ligne")


def _hors_ligne(cle: str, tolerance: int, aujourdhui: date, etat_path: Path) -> ResultatLicence:
    """Serveur injoignable : applique la tolérance hors-ligne de N jours."""
    derniere = _lire_derniere_verif(etat_path)
    if derniere is None:
        return ResultatLicence(
            False,
            "Licence non vérifiable : serveur injoignable et aucune vérification "
            "réussie antérieure. Connectez-vous à Internet au moins une fois. "
            + _contact(),
            "bloque",
        )
    jours = (aujourdhui - derniere).days
    if jours <= tolerance:
        restant = max(0, tolerance - jours)
        return ResultatLicence(
            True,
            f"Mode hors-ligne (dernière vérification le {derniere.isoformat()}, "
            f"{restant} j de tolérance restants).",
            "hors-ligne",
        )
    return ResultatLicence(
        False,
        f"Hors-ligne depuis trop longtemps (dernière vérification le "
        f"{derniere.isoformat()}, tolérance de {tolerance} j dépassée). "
        "Connectez-vous à Internet. " + _contact(),
        "bloque",
    )
