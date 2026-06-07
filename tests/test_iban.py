"""Tests du module IBAN (validation mod 97 + clé RIB + décomposition)."""

import pytest

from src.iban import (
    IbanInvalide,
    bic_valide,
    cle_rib_valide,
    decomposer_fr,
    formater_affichage,
    generer_iban_fr,
    iban_valide,
    normaliser,
    valider_pour_mandat,
)

# IBAN français réel de référence publique (exemple BNP, contient une lettre).
IBAN_REF = "FR1420041010050500013M02606"


def test_iban_reference_valide():
    assert iban_valide(IBAN_REF)


def test_iban_reference_avec_espaces():
    assert iban_valide("FR14 2004 1010 0505 0001 3M02 606")


def test_iban_cle_fausse_invalide():
    # On casse la clé de contrôle (14 -> 15).
    assert not iban_valide("FR1520041010050500013M02606")


def test_iban_vide_ou_bidon():
    assert not iban_valide("")
    assert not iban_valide("BONJOUR")
    assert not iban_valide("FR00")


def test_generer_iban_fr_est_valide():
    iban = generer_iban_fr("30004", "00001", "00001234567")
    assert iban_valide(iban)
    assert iban.startswith("FR") and len(iban) == 27


def test_decomposer_fr():
    iban = generer_iban_fr("30004", "00001", "00001234567")
    rib = decomposer_fr(iban)
    assert rib.banque == "30004"
    assert rib.guichet == "00001"
    assert rib.compte == "00001234567"
    # clé RIB cohérente
    assert cle_rib_valide(rib.banque, rib.guichet, rib.compte, rib.cle_rib)


def test_decomposer_refuse_non_fr():
    with pytest.raises(IbanInvalide):
        decomposer_fr("DE89370400440532013000")


def test_valider_pour_mandat_ok():
    iban = generer_iban_fr("30004", "00001", "00001234567")
    rib = valider_pour_mandat(iban)
    assert rib.banque == "30004"


def test_valider_pour_mandat_refuse_iban_invalide():
    with pytest.raises(IbanInvalide, match="mod 97"):
        valider_pour_mandat("FR1520041010050500013M02606")


def test_valider_pour_mandat_refuse_cle_rib_fausse():
    # IBAN dont la clé de contrôle est correcte mais la clé RIB fausse.
    # On part d'un IBAN valide et on modifie la clé RIB (2 derniers chiffres)
    # puis on recalcule la clé IBAN pour qu'elle reste cohérente.
    from src.iban import cle_iban

    rib = decomposer_fr(generer_iban_fr("30004", "00001", "00001234567"))
    mauvaise_cle = "00" if rib.cle_rib != "00" else "01"
    bban = f"{rib.banque}{rib.guichet}{rib.compte}{mauvaise_cle}"
    iban_casse = f"FR{cle_iban('FR', bban)}{bban}"
    assert iban_valide(iban_casse)  # mod 97 OK
    with pytest.raises(IbanInvalide, match="RIB"):
        valider_pour_mandat(iban_casse)


def test_formater_affichage():
    iban = generer_iban_fr("30004", "00001", "00001234567")
    aff = formater_affichage(iban)
    assert aff.startswith("FR")
    assert "  " not in aff  # blocs séparés par un seul espace
    assert normaliser(aff) == iban


# --------------------------------------------------------------------------- #
# Validation BIC
# --------------------------------------------------------------------------- #
def test_bic_valide_11_et_8():
    assert bic_valide("BNPAFRPPXXX")   # 11 car.
    assert bic_valide("AGRIFRPP")      # 8 car.
    assert bic_valide("bnpafrpp xxx")  # espaces + minuscules tolérés


def test_bic_invalide_mauvaise_longueur():
    assert not bic_valide("BNPAFR")      # trop court
    assert not bic_valide("BNPAFRPPXX")  # 10 car. (ni 8 ni 11)


def test_bic_invalide_pays_inexistant():
    # « IDENTITE » a la bonne forme (8 lettres) mais le pays « TI » n'existe pas.
    assert not bic_valide("IDENTITE")


def test_bic_invalide_chiffres_dans_la_banque():
    assert not bic_valide("BNP1FRPP")  # les 6 premiers doivent être des lettres


def test_bic_vide():
    assert not bic_valide("")
