"""Validation et décomposition d'IBAN — usage mandat SEPA (Les Menus Services).

⚠️ RGPD (CLAUDE.md §9) : l'IBAN/BIC NE SONT JAMAIS PERSISTÉS. Ce module ne fait
que valider et décomposer en mémoire ; aucune écriture en base.

Deux contrôles indépendants (CLAUDE.md §9 + décision client) :
  1. Clé de contrôle IBAN (mod 97) — détecte toute faute de saisie/OCR.
  2. Clé RIB française (BBAN) — sécurité supplémentaire propre aux comptes FR.

Décomposition d'un IBAN français (27 caractères) :
  FR | 2 (clé IBAN) | 5 (code banque) | 5 (code guichet) | 11 (n° compte) | 2 (clé RIB)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Lettre -> valeur pour le mod 97 IBAN (A=10 … Z=35).
_VAL_IBAN = {chr(ord("A") + i): str(10 + i) for i in range(26)}

# Lettre -> chiffre pour le calcul de la clé RIB française (compte alphanumérique).
_VAL_RIB = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8, "I": 9,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "O": 6, "P": 7, "Q": 8, "R": 9,
    "S": 2, "T": 3, "U": 4, "V": 5, "W": 6, "X": 7, "Y": 8, "Z": 9,
}


class IbanInvalide(ValueError):
    """Levée quand un IBAN/clé RIB échoue à la validation (génération refusée)."""


@dataclass(frozen=True)
class RibFr:
    """Décomposition d'un IBAN français en blocs RIB classiques."""

    banque: str    # 5 chiffres (code établissement)
    guichet: str   # 5 chiffres (code guichet)
    compte: str    # 11 caractères (n° de compte)
    cle_rib: str   # 2 chiffres (clé RIB)


# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #
def normaliser(iban: str) -> str:
    """Supprime espaces/séparateurs et met en majuscules."""
    return re.sub(r"[\s ]+", "", iban).upper()


def formater_affichage(iban: str) -> str:
    """Regroupe l'IBAN par blocs de 4 pour l'affichage : FR76 3000 4000 …"""
    iban = normaliser(iban)
    return " ".join(iban[i : i + 4] for i in range(0, len(iban), 4))


# --------------------------------------------------------------------------- #
# Validation IBAN (mod 97)
# --------------------------------------------------------------------------- #
def _vers_numerique(s: str) -> str:
    return "".join(_VAL_IBAN.get(c, c) for c in s)


def iban_valide(iban: str) -> bool:
    """Vrai si la clé de contrôle IBAN (mod 97) est correcte."""
    iban = normaliser(iban)
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]+", iban or ""):
        return False
    réarrangé = iban[4:] + iban[:4]
    return int(_vers_numerique(réarrangé)) % 97 == 1


def cle_iban(pays: str, bban: str) -> str:
    """Calcule les 2 chiffres de clé IBAN pour un pays + BBAN donnés."""
    réarrangé = _vers_numerique(bban) + _vers_numerique(pays) + "00"
    return f"{98 - int(réarrangé) % 97:02d}"


# --------------------------------------------------------------------------- #
# Clé RIB française
# --------------------------------------------------------------------------- #
def _compte_numerique(compte: str) -> int:
    return int("".join(str(_VAL_RIB.get(c, c)) for c in compte.upper()))


def calculer_cle_rib(banque: str, guichet: str, compte: str) -> str:
    """Calcule la clé RIB (2 chiffres) à partir des blocs banque/guichet/compte."""
    b, g, c = int(banque), int(guichet), _compte_numerique(compte)
    cle = 97 - (89 * b + 15 * g + 3 * c) % 97
    return f"{cle:02d}"


def cle_rib_valide(banque: str, guichet: str, compte: str, cle_rib: str) -> bool:
    """Vrai si (89·banque + 15·guichet + 3·compte + clé) ≡ 0 [97]."""
    b, g, c, k = int(banque), int(guichet), _compte_numerique(compte), int(cle_rib)
    return (89 * b + 15 * g + 3 * c + k) % 97 == 0


# --------------------------------------------------------------------------- #
# Décomposition FR
# --------------------------------------------------------------------------- #
def decomposer_fr(iban: str) -> RibFr:
    """Décompose un IBAN français en blocs RIB. Lève IbanInvalide si non FR/27."""
    iban = normaliser(iban)
    if not iban.startswith("FR") or len(iban) != 27:
        raise IbanInvalide(
            f"IBAN non français ou longueur invalide ({len(iban)} ≠ 27) : "
            "décomposition RIB impossible."
        )
    bban = iban[4:]  # 23 caractères : 5 + 5 + 11 + 2
    return RibFr(
        banque=bban[0:5],
        guichet=bban[5:10],
        compte=bban[10:21],
        cle_rib=bban[21:23],
    )


def valider_pour_mandat(iban: str) -> RibFr:
    """Valide un IBAN FR pour le mandat : mod 97 PUIS clé RIB.

    Retourne la décomposition RIB si tout est valide ; sinon lève IbanInvalide
    avec un message précis (la génération du mandat doit alors être refusée).
    """
    if not iban_valide(iban):
        raise IbanInvalide(
            "Clé de contrôle IBAN incorrecte (mod 97) — IBAN mal saisi ou mal lu."
        )
    rib = decomposer_fr(iban)
    if not cle_rib_valide(rib.banque, rib.guichet, rib.compte, rib.cle_rib):
        raise IbanInvalide(
            "Clé RIB française incorrecte — incohérence banque/guichet/compte/clé."
        )
    return rib


def generer_iban_fr(banque: str, guichet: str, compte: str) -> str:
    """Construit un IBAN FR complet et VALIDE (clé RIB + clé IBAN calculées).

    Utilitaire de TEST (génère des IBAN fictifs valides).
    """
    cle_rib = calculer_cle_rib(banque, guichet, compte)
    bban = f"{banque}{guichet}{compte}{cle_rib}"
    return f"FR{cle_iban('FR', bban)}{bban}"
