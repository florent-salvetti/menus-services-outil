"""Tests du moteur de calcul — cas de référence du CLAUDE.md §7.

Le cas de référence DOIT tomber exactement :
    Menus du marché 4C ×6 + Menus du jour 5C ×4
    → hebdo TTC 130,80 / HT 118,91
    → repas TTC 65,91 / service TTC 64,89 (somme = total)
    → mensuel 566,80 → reste à charge après crédit d'impôt 426,21

NB : le crédit de 50 % porte UNIQUEMENT sur la part service (colonne apres_ci
de la grille), pas sur la part repas. Le reste à charge n'est donc PAS
566,80/2 = 283,40 (ancienne règle §7 erronée) mais 426,21.
"""

from decimal import Decimal
from pathlib import Path

import pytest

from src.calcul import (
    arrondi,
    calculer,
    charger_grille,
    fmt_eur,
)

GRILLE_PATH = Path(__file__).resolve().parent.parent / "tarifs.json"


@pytest.fixture(scope="module")
def grille():
    return charger_grille(GRILLE_PATH)


@pytest.fixture
def resultat_reference(grille):
    saisie = [
        ("Menus du marché 4C", 6),
        ("Menus du jour 5C", 4),
    ]
    return calculer(saisie, grille)


# --------------------------------------------------------------------------- #
# Cas de référence §7 — valeurs exactes
# --------------------------------------------------------------------------- #
def test_total_hebdo_ttc(resultat_reference):
    assert arrondi(resultat_reference.total_hebdo_ttc) == Decimal("130.80")


def test_total_hebdo_ht(resultat_reference):
    assert arrondi(resultat_reference.total_hebdo_ht) == Decimal("118.91")


def test_total_repas_ttc(resultat_reference):
    assert arrondi(resultat_reference.total_repas_ttc) == Decimal("65.91")


def test_total_service_ttc(resultat_reference):
    assert arrondi(resultat_reference.total_service_ttc) == Decimal("64.89")


def test_invariant_repas_plus_service_egale_total(resultat_reference):
    # service_ttc + repas_ttc == ttc (à l'arrondi près) — invariant CLAUDE.md §5
    somme = resultat_reference.total_repas_ttc + resultat_reference.total_service_ttc
    assert arrondi(somme) == arrondi(resultat_reference.total_hebdo_ttc)


def test_repas_service_ht(resultat_reference):
    assert arrondi(resultat_reference.total_repas_ht) == Decimal("59.92")
    assert arrondi(resultat_reference.total_service_ht) == Decimal("58.99")


def test_cout_mensuel(resultat_reference):
    assert arrondi(resultat_reference.cout_mensuel_ttc) == Decimal("566.80")


def test_total_apres_credit_impot(resultat_reference):
    # Crédit sur la part service uniquement (colonne apres_ci) :
    #   Menus du marché 4C : 9,612 × 6 = 57,672
    #   Menus du jour 5C   : 10,171 × 4 = 40,684
    #   hebdo = 98,356 → mensuel × 52/12 = 426,21
    assert arrondi(resultat_reference.total_apres_ci) == Decimal("426.21")


def test_credit_impot_mensuel(resultat_reference):
    # Le crédit = coût mensuel - reste à charge = 566,80 - 426,21 = 140,59
    # (= 50 % de la part service mensuelle).
    assert arrondi(resultat_reference.credit_impot_mensuel) == Decimal("140.59")


def test_nb_repas_total(resultat_reference):
    assert resultat_reference.nb_repas_total == 10


def test_pas_d_avertissement_sur_le_cas_reference(resultat_reference):
    # Les deux formules sont éligibles au crédit d'impôt → aucun flag.
    assert resultat_reference.avertissements == []


# --------------------------------------------------------------------------- #
# Crédit d'impôt « à vérifier » — le Pain (apres_ci absent)
# --------------------------------------------------------------------------- #
def test_pain_remonte_un_avertissement(grille):
    res = calculer([("Menus du marché 4C", 6), ("Pain", 6)], grille)
    assert any("Pain" in a and "à vérifier" in a for a in res.avertissements)


def test_pain_compte_plein_tarif_dans_reste_a_charge(grille):
    # Ligne éligible : reste à charge = q × apres_ci (part service créditée).
    # Pain non éligible : compté PLEIN TARIF (aucun crédit).
    res = calculer([("Menus du marché 4C", 6), ("Pain", 6)], grille)
    hebdo_eligible = Decimal("9.612") * 6        # apres_ci des Menus
    hebdo_pain = Decimal("0.25") * 6             # plein tarif (ttc)
    mensuel_attendu = (hebdo_eligible + hebdo_pain) * (Decimal(52) / Decimal(12))
    assert arrondi(res.total_apres_ci) == arrondi(mensuel_attendu)


def test_pain_non_ventile_repas_service(grille):
    # Pain : repas_ttc renseigné mais service_ttc null → ligne non ventilable,
    # donc exclue des sommes repas ET service.
    res = calculer([("Pain", 6)], grille)
    assert res.total_repas_ttc == Decimal(0)
    assert res.total_service_ttc == Decimal(0)


# --------------------------------------------------------------------------- #
# Prestations de service : éligibles (ont un apres_ci), sans ventilation
# --------------------------------------------------------------------------- #
def test_menage_eligible_sans_avertissement(grille):
    res = calculer([("Ménage", 2)], grille)
    assert res.avertissements == []  # Ménage a un apres_ci → éligible
    assert res.total_service_ttc == Decimal(0)  # mais pas de ventilation


# --------------------------------------------------------------------------- #
# Cas mono-formule
# --------------------------------------------------------------------------- #
def test_mono_formule(grille):
    res = calculer([("Menus du marché 4C", 6)], grille)
    assert arrondi(res.total_hebdo_ttc) == Decimal("76.80")
    assert arrondi(res.cout_mensuel_ttc) == Decimal("332.80")


# --------------------------------------------------------------------------- #
# Formatage français
# --------------------------------------------------------------------------- #
def test_fmt_eur():
    # Espaces insécables ( ) — typographie française.
    assert fmt_eur(Decimal("130.8")) == "130,80 €"
    assert fmt_eur(Decimal("283.4")) == "283,40 €"
    assert fmt_eur(Decimal("1234.5")) == "1 234,50 €"


# --------------------------------------------------------------------------- #
# Réduction commerciale (Remise)
# --------------------------------------------------------------------------- #
def test_remise_pourcent_reduit_tous_les_totaux(grille):
    from src.calcul import Remise

    saisie = [("Menus du marché 4C", 6), ("Menus du jour 5C", 4)]
    res = calculer(saisie, grille, remise=Remise("pourcent", Decimal("10")))
    assert arrondi(res.prix_public_hebdo_ttc) == Decimal("130.80")
    assert arrondi(res.remise_hebdo_ttc) == Decimal("13.08")
    assert arrondi(res.total_hebdo_ttc) == Decimal("117.72")
    # Invariant conservé : repas + service = total (à l'arrondi près)
    assert arrondi(res.total_repas_ttc + res.total_service_ttc) == arrondi(res.total_hebdo_ttc)
    # Reste à charge réduit dans la même proportion (426,21 × 0,9)
    assert arrondi(res.total_apres_ci) == Decimal("383.59")
    # Crédit d'impôt = mensuel − reste à charge
    assert arrondi(res.credit_impot_mensuel) == arrondi(res.cout_mensuel_ttc - res.total_apres_ci)


def test_remise_euros_par_semaine(grille):
    from src.calcul import Remise

    res = calculer([("Menus du marché 4C", 6)], grille, remise=Remise("euros", Decimal("6.80")))
    assert arrondi(res.prix_public_hebdo_ttc) == Decimal("76.80")
    assert arrondi(res.remise_hebdo_ttc) == Decimal("6.80")
    assert arrondi(res.total_hebdo_ttc) == Decimal("70.00")


def test_remise_superieure_au_total_est_plafonnee(grille):
    from src.calcul import Remise

    res = calculer([("Menus du marché 4C", 6)], grille, remise=Remise("euros", Decimal("999")))
    assert arrondi(res.total_hebdo_ttc) == Decimal("0.00")
    assert any("plafonnée" in a for a in res.avertissements)


def test_sans_remise_pas_de_changement(resultat_reference):
    assert resultat_reference.remise is None
    assert resultat_reference.remise_hebdo_ttc == 0
    assert arrondi(resultat_reference.prix_public_hebdo_ttc) == Decimal("130.80")
