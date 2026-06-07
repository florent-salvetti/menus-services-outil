"""Tests de l'EXTRACTION OCR (pure, sans Tesseract).

On simule des sorties Tesseract (propres et bruitées) et on vérifie que
extraire_iban / extraire_bic retrouvent les bonnes valeurs. Le moteur Tesseract
lui-même n'est pas testé ici (binaire externe embarqué, validé sur vrai scan).
"""

import pytest

from src.iban import formater_affichage, generer_iban_fr, iban_valide
from src.ocr.rib import extraire_bic, extraire_iban

# IBAN FR fictif mais VALIDE pour les simulations.
IBAN = generer_iban_fr("30004", "00001", "00001234567")  # FR76 3000 4000 0100 0012 3456 789
BIC = "BNPAFRPPXXX"


# --------------------------------------------------------------------------- #
# IBAN — lecture propre
# --------------------------------------------------------------------------- #
def test_iban_propre_avec_espaces():
    texte = f"IBAN : {formater_affichage(IBAN)}\nBIC : {BIC}\n"
    assert extraire_iban(texte) == IBAN


def test_iban_propre_sans_espaces():
    texte = f"Domiciliation BNP\n{IBAN}\nTitulaire : Mme MARTIN"
    assert extraire_iban(texte) == IBAN


def test_iban_multi_lignes_bruit_autour():
    texte = (
        "RELEVE D'IDENTITE BANCAIRE\n"
        "Code banque 30004  Code guichet 00001\n"
        f"IBAN  {formater_affichage(IBAN)}\n"
        "Le present releve est destine a etre remis ...\n"
    )
    assert extraire_iban(texte) == IBAN


# --------------------------------------------------------------------------- #
# IBAN — lecture bruitée : PAS de correction silencieuse (sécurité)
# --------------------------------------------------------------------------- #
def _injecter(iban: str, remplacements: dict[int, str]) -> str:
    chars = list(iban)
    for i, c in remplacements.items():
        chars[i] = c
    return "".join(chars)


def test_iban_bruite_renvoye_brut_et_invalide():
    # 2 confusions OCR ('5'->'S', '8'->'B'). On NE corrige PAS en douce (ça
    # pourrait fabriquer un IBAN valide mais FAUX). On renvoie le brut, invalide,
    # pour que l'humain corrige (mod 97 ✗ affiché dans l'UI).
    i5, i8 = IBAN.index("5"), IBAN.index("8")
    bruite = _injecter(IBAN, {i5: "S", i8: "B"})
    res = extraire_iban(f"IBAN {bruite}")
    assert res == bruite
    assert not iban_valide(res)


def test_iban_tres_bruite_renvoie_candidat_invalide():
    # Beaucoup de '0' lus 'O' : candidat renvoyé (27 car., FR…), invalide.
    bruite = IBAN.replace("0", "O")
    res = extraire_iban(f"IBAN {bruite}")
    assert res is not None
    assert res.startswith("FR") and len(res) == 27
    assert not iban_valide(res)


# --------------------------------------------------------------------------- #
# IBAN — robustesse / faux positifs
# --------------------------------------------------------------------------- #
def test_pas_d_iban_renvoie_none():
    assert extraire_iban("Aucune coordonnee bancaire ici.") is None


def test_mot_france_n_est_pas_un_iban():
    # « FRANCE » commence par FR mais le caractère suivant n'est pas un chiffre.
    assert extraire_iban("Adresse en FRANCE, ville d'Orange.") is None


def test_fr_suivi_de_mots_n_est_pas_un_iban():
    assert extraire_iban("FR : votre releve bancaire ci-dessous") is None


# --------------------------------------------------------------------------- #
# BIC
# --------------------------------------------------------------------------- #
def test_bic_avec_label():
    assert extraire_bic(f"BIC : {BIC}\n") == BIC


def test_bic_swift_label():
    assert extraire_bic(f"Code SWIFT {BIC}") == BIC


def test_bic_8_caracteres():
    assert extraire_bic("BIC AGRIFRPP") == "AGRIFRPP"


def test_bic_absent():
    assert extraire_bic("Pas de code ici 12345") is None


def test_bic_rib_credit_mutuel_reel():
    # Cas réel : le titre contient « IDENTITE » (pays TI inexistant -> écarté)
    # ET « BANCAIRE » (pays AI valide -> piège), mais le vrai BIC « CMCIFR2A »
    # suit le libellé « BIC (Bank Identifier Code) ».
    texte = (
        "RELEVE D'IDENTITE BANCAIRE\n"
        "IBAN FR76 1027 8060 4100 0204 1590 123\n"
        "BIC (Bank Identifier Code)  CMCIFR2A\n"
        "Titulaire : M. DURAND\n"
    )
    assert extraire_bic(texte) == "CMCIFR2A"


def test_bic_identite_seul_rejete():
    # « IDENTITE » seul (pays TI) -> aucun BIC valide.
    assert extraire_bic("RELEVE D'IDENTITE") is None
