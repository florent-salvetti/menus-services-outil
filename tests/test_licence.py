"""Tests de la vérification de licence (kill switch §15), sans réseau.

Le `lecteur` est injecté (réponse simulée ou exception = serveur injoignable),
`aujourdhui` et `etat_path` aussi -> tests déterministes.
"""

import json
from datetime import date, timedelta

import pytest

from src.licence import charger_config, verifier

CLE = "MICHAEL-ORANGE-2026"
URL = "https://exemple/licences.json"  # non appelé : lecteur injecté
AUJ = date(2026, 6, 7)


def _config(tolerance=5):
    return {"licence": {"cle": CLE, "url_statut": URL, "tolerance_hors_ligne_jours": tolerance}}


def _serveur(actif=True, echeance="2026-12-31", cle=CLE):
    """Fabrique un lecteur renvoyant un licences.json simulé."""
    contenu = json.dumps({cle: {"actif": actif, "echeance": echeance, "client": "Orange"}})
    return lambda url: contenu


def _injoignable(url):
    raise ConnectionError("serveur injoignable (simulé)")


def _etat_avec_date(tmp_path, jour: date):
    p = tmp_path / "licence_etat.json"
    p.write_text(json.dumps({"derniere_verif_reussie": jour.isoformat()}), encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# Serveur joignable : décision définitive
# --------------------------------------------------------------------------- #
def test_verif_reussie_autorise_et_memorise(tmp_path):
    etat = tmp_path / "etat.json"
    res = verifier(_config(), lecteur=_serveur(), aujourdhui=AUJ, etat_path=etat)
    assert res.autorise and res.mode == "en-ligne"
    # date de vérif réussie mémorisée
    assert json.loads(etat.read_text())["derniere_verif_reussie"] == AUJ.isoformat()


def test_licence_desactivee_bloque(tmp_path):
    res = verifier(_config(), lecteur=_serveur(actif=False), aujourdhui=AUJ, etat_path=tmp_path / "e.json")
    assert not res.autorise and res.mode == "bloque"
    assert "désactivée" in res.message


def test_echeance_depassee_bloque(tmp_path):
    res = verifier(_config(), lecteur=_serveur(echeance="2026-01-01"), aujourdhui=AUJ, etat_path=tmp_path / "e.json")
    assert not res.autorise and res.mode == "bloque"
    assert "expirée" in res.message


def test_cle_absente_bloque(tmp_path):
    # Le serveur répond mais la clé du client n'y figure pas.
    res = verifier(_config(), lecteur=_serveur(cle="AUTRE-CLE"), aujourdhui=AUJ, etat_path=tmp_path / "e.json")
    assert not res.autorise and res.mode == "bloque"
    assert "inconnue" in res.message


def test_serveur_repond_ne_met_pas_a_jour_etat_si_bloque(tmp_path):
    etat = tmp_path / "etat.json"
    verifier(_config(), lecteur=_serveur(actif=False), aujourdhui=AUJ, etat_path=etat)
    assert not etat.exists()  # un blocage ne mémorise pas de vérif réussie


# --------------------------------------------------------------------------- #
# Config inexploitable : blocage strict
# --------------------------------------------------------------------------- #
def test_config_absente_bloque(tmp_path):
    res = verifier({}, lecteur=_serveur(), aujourdhui=AUJ, etat_path=tmp_path / "e.json")
    assert not res.autorise and res.mode == "bloque"
    assert "non configurée" in res.message


def test_cle_manquante_bloque(tmp_path):
    cfg = {"licence": {"cle": "", "url_statut": URL}}
    res = verifier(cfg, lecteur=_serveur(), aujourdhui=AUJ, etat_path=tmp_path / "e.json")
    assert not res.autorise and res.mode == "bloque"


# --------------------------------------------------------------------------- #
# Serveur injoignable : tolérance hors-ligne
# --------------------------------------------------------------------------- #
def test_hors_ligne_dans_la_tolerance_autorise(tmp_path):
    etat = _etat_avec_date(tmp_path, AUJ - timedelta(days=3))  # 3 j <= 5
    res = verifier(_config(tolerance=5), lecteur=_injoignable, aujourdhui=AUJ, etat_path=etat)
    assert res.autorise and res.mode == "hors-ligne"
    assert "tolérance" in res.message


def test_hors_ligne_limite_exacte_autorise(tmp_path):
    etat = _etat_avec_date(tmp_path, AUJ - timedelta(days=5))  # 5 j == tolérance
    res = verifier(_config(tolerance=5), lecteur=_injoignable, aujourdhui=AUJ, etat_path=etat)
    assert res.autorise and res.mode == "hors-ligne"


def test_hors_ligne_au_dela_bloque(tmp_path):
    etat = _etat_avec_date(tmp_path, AUJ - timedelta(days=6))  # 6 j > 5
    res = verifier(_config(tolerance=5), lecteur=_injoignable, aujourdhui=AUJ, etat_path=etat)
    assert not res.autorise and res.mode == "bloque"
    assert "trop longtemps" in res.message


def test_hors_ligne_sans_verif_anterieure_bloque(tmp_path):
    # Serveur injoignable ET aucune vérif réussie passée -> blocage.
    res = verifier(_config(), lecteur=_injoignable, aujourdhui=AUJ, etat_path=tmp_path / "absent.json")
    assert not res.autorise and res.mode == "bloque"


def test_config_avec_bom_se_charge(tmp_path):
    # Un config.json édité sous Windows peut commencer par un BOM UTF-8.
    # charger_config (utf-8-sig) doit le tolérer (sinon licence "non configurée").
    p = tmp_path / "config.json"
    p.write_bytes(b"\xef\xbb\xbf" + json.dumps({"licence": {"cle": "X"}}).encode("utf-8"))
    assert charger_config(p).get("licence", {}).get("cle") == "X"


def test_json_illisible_traite_comme_hors_ligne(tmp_path):
    # Réponse reçue mais JSON corrompu -> traité comme injoignable (tolérance).
    etat = _etat_avec_date(tmp_path, AUJ - timedelta(days=1))
    res = verifier(_config(), lecteur=lambda u: "{pas du json", aujourdhui=AUJ, etat_path=etat)
    assert res.autorise and res.mode == "hors-ligne"
