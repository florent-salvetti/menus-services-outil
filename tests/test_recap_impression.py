"""Tests du récapitulatif copiable et de la fusion PDF (sans LibreOffice)."""

from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from src.calcul import calculer, charger_grille
from src.dossier import LignePrestation, SaisieDossier, recapitulatif
from src import impression

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def resultat():
    grille = charger_grille(RACINE / "tarifs.json")
    return calculer([("Menus du marché 4C", 6), ("Menus du jour 5C", 4)], grille)


def _saisie(**kw) -> SaisieDossier:
    base = dict(
        civilite="Mme", prenom="Jeanne", nom="Martin",
        adresse="12 rue des Lilas", cp="84100", ville="Orange",
        benef_identique=True,
        lignes=[LignePrestation("Menus du marché 4C", 6), LignePrestation("Menus du jour 5C", 4)],
        tournee="T1", jours_repas=["Lundi", "Jeudi"],
        devis_num="2026-0001", date_devis="07/06/2026",
        iban="FR7630004000010000123456789",
    )
    base.update(kw)
    return SaisieDossier(**base)


# --------------------------------------------------------------------------- #
# Récapitulatif
# --------------------------------------------------------------------------- #
def test_recap_contient_le_bon_reste_a_charge(resultat):
    txt = recapitulatif(_saisie(), resultat)
    assert "426,21" in txt           # reste à charge correct
    assert "283,40" not in txt       # AUCUNE trace de l'ancien calcul erroné


def test_recap_montants_et_formules(resultat):
    txt = recapitulatif(_saisie(), resultat)
    assert "130,80" in txt
    assert "Menus du marché 4C ×6" in txt
    assert "Menus du jour 5C ×4" in txt
    assert "10 repas/sem." in txt


def test_recap_iban_avec_mention_non_conserve(resultat):
    txt = recapitulatif(_saisie(), resultat)
    assert "FR76 3000 4000 0100 0012 3456 789" in txt
    assert "non conservé par l'outil" in txt


def test_recap_sans_iban(resultat):
    txt = recapitulatif(_saisie(iban=""), resultat)
    assert "IBAN" not in txt


def test_recap_beneficiaire_masque_si_identique(resultat):
    assert "BÉNÉFICIAIRE" not in recapitulatif(_saisie(benef_identique=True), resultat)


def test_recap_beneficiaire_affiche_si_different(resultat):
    txt = recapitulatif(
        _saisie(benef_identique=False, benef_prenom="Jean", benef_nom="Martin",
                benef_adresse="5 chemin du Moulin"),
        resultat,
    )
    assert "BÉNÉFICIAIRE" in txt
    assert "Jean Martin" in txt
    assert "5 chemin du Moulin" in txt


# --------------------------------------------------------------------------- #
# Fusion PDF (pypdf, sans LibreOffice)
# --------------------------------------------------------------------------- #
def _pdf_blanc(chemin: Path, pages: int = 1) -> Path:
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=200, height=200)
    with open(chemin, "wb") as fh:
        w.write(fh)
    return chemin


def test_fusion_pdf_ordre_et_pages(tmp_path):
    # 3 PDF (1, 2, 3 pages) -> fusion = 6 pages, dans l'ordre.
    pdfs = [
        _pdf_blanc(tmp_path / "a.pdf", 1),
        _pdf_blanc(tmp_path / "b.pdf", 2),
        _pdf_blanc(tmp_path / "c.pdf", 3),
    ]
    sortie = tmp_path / "fusion.pdf"
    writer = PdfWriter()
    for p in pdfs:
        writer.append(str(p))
    with open(sortie, "wb") as fh:
        writer.write(fh)
    assert len(PdfReader(str(sortie)).pages) == 6


def test_trouver_soffice_absent_leve_erreur(monkeypatch):
    # Ni embarqué ni config.json -> SofficeIntrouvable avec message clair.
    monkeypatch.setattr(impression, "_SOFFICE_EMBARQUE", RACINE / "libreoffice" / "program" / "soffice.exe")
    monkeypatch.setattr(impression, "_CONFIG", RACINE / "config.json")
    if not impression._SOFFICE_EMBARQUE.exists() and not impression._CONFIG.exists():
        with pytest.raises(impression.SofficeIntrouvable):
            impression.trouver_soffice()
