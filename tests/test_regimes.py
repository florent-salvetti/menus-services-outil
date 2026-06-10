"""Tests du module regimes (liste éditable des régimes particuliers)."""

import json

import pytest

from src.regimes import REGIMES_DEFAUT, charger_regimes, enregistrer_regimes


def test_defaut_si_fichier_absent(tmp_path):
    assert charger_regimes(tmp_path / "absent.json") == REGIMES_DEFAUT


def test_defaut_si_fichier_corrompu(tmp_path):
    f = tmp_path / "regimes.json"
    f.write_text("{pas du json", encoding="utf-8")
    assert charger_regimes(f) == REGIMES_DEFAUT


def test_defaut_si_liste_vide(tmp_path):
    f = tmp_path / "regimes.json"
    f.write_text("[]", encoding="utf-8")
    assert charger_regimes(f) == REGIMES_DEFAUT


def test_round_trip(tmp_path):
    f = tmp_path / "regimes.json"
    enregistrer_regimes(["végétarien", "sans gluten"], f)
    assert charger_regimes(f) == ["végétarien", "sans gluten"]


def test_bom_tolere(tmp_path):
    # regimes.json peut être édité à la main (Notepad ajoute un BOM).
    f = tmp_path / "regimes.json"
    f.write_text(json.dumps(["mixé"], ensure_ascii=False), encoding="utf-8-sig")
    assert charger_regimes(f) == ["mixé"]


def test_nettoyage_doublons_et_vides(tmp_path):
    f = tmp_path / "regimes.json"
    ecrits = enregistrer_regimes(["  mixé ", "", "mixé", "Mixé", "sans sel"], f)
    # Doublons (insensibles à la casse) et vides retirés, ordre conservé.
    assert ecrits == ["mixé", "sans sel"]
    assert charger_regimes(f) == ["mixé", "sans sel"]


def test_liste_vide_refusee(tmp_path):
    f = tmp_path / "regimes.json"
    with pytest.raises(ValueError):
        enregistrer_regimes(["", "   "], f)
    assert not f.exists()  # rien n'a été écrit


def test_backup_avant_ecriture(tmp_path):
    f = tmp_path / "regimes.json"
    enregistrer_regimes(["diabétique"], f)
    enregistrer_regimes(["sans sel"], f)
    bak = tmp_path / "regimes.json.bak"
    assert bak.exists()
    assert json.loads(bak.read_text(encoding="utf-8")) == ["diabétique"]
