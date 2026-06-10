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
        devis_num="10062026-1", date_devis="07/06/2026",
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


def test_recap_jamais_d_iban(resultat):
    # Plus AUCUNE coordonnée bancaire dans l'outil (demande client) :
    # le prélèvement rappelle juste que le RIB est à joindre.
    txt = recapitulatif(_saisie(mode_paiement="prelevement"), resultat)
    assert "IBAN" not in txt
    assert "RIB à joindre" in txt


def test_recap_mode_paiement(resultat):
    assert "Prélèvement automatique" in recapitulatif(
        _saisie(mode_paiement="prelevement"), resultat
    )
    assert "Chèque bancaire" in recapitulatif(_saisie(mode_paiement="cheque"), resultat)
    assert "PAIEMENT" not in recapitulatif(_saisie(), resultat)


def test_recap_tutelle(resultat):
    txt = recapitulatif(
        _saisie(tutelle=True, tutelle_organisme="UDAF 84",
                tuteur_prenom="Jean", tuteur_nom="DUPONT"),
        resultat,
    )
    assert "TUTELLE" in txt
    assert "Jean DUPONT" in txt
    assert "UDAF 84" in txt
    assert "TUTELLE" not in recapitulatif(_saisie(), resultat)


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


def test_trouver_soffice_absent_leve_erreur():
    # Ni embarqué ni config.json -> SofficeIntrouvable avec message clair.
    if not impression._SOFFICE_EMBARQUE.exists() and not impression._CONFIG.exists():
        with pytest.raises(impression.SofficeIntrouvable):
            impression.trouver_soffice()


def _docx_minimal(chemin: Path) -> Path:
    from docx import Document
    d = Document()
    d.add_paragraph("Test impression")
    d.save(str(chemin))
    return chemin


def test_pdf_dossier_complet_sans_docx_leve_valueerror(tmp_path):
    with pytest.raises(ValueError):
        impression.pdf_dossier_complet([], tmp_path / "x.pdf")


def test_conversion_echec_leve_conversion_impossible(tmp_path):
    # On force LibreOffice avec un soffice inexistant -> aucun convertisseur
    # n'aboutit -> ConversionImpossible (déterministe, que Word soit là ou non).
    docx = _docx_minimal(tmp_path / "doc.docx")
    with pytest.raises(impression.ConversionImpossible) as exc:
        impression.convertir([docx], tmp_path, soffice=tmp_path / "soffice_absent.exe",
                              moteur="libreoffice")
    # Message non bloquant : rappelle que les .docx restent disponibles.
    assert ".docx" in str(exc.value)


def test_recap_regime_au_bout_du_nom():
    grille = charger_grille(RACINE / "tarifs.json")
    res = calculer([("Menus du marché 4C", 6, "sans sel")], grille)
    txt = recapitulatif(_saisie(lignes=[LignePrestation("Menus du marché 4C", 6, "sans sel")]), res)
    assert "Menus du marché 4C – sans sel ×6" in txt
