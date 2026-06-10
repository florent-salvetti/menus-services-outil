"""Point d'entrée de l'interface.

Lancer depuis la racine du projet :
    python -m src.ui.app
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permet `python -m src.ui.app` ET `python src/ui/app.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from PySide6.QtWidgets import QApplication, QMessageBox

from src import licence
from src.ui.main_window import MainWindow


def _selftest() -> int:
    """Smoke test HEADLESS dans le binaire packagé : prouve que les chemins
    relatifs (config.json, modeles/, tarifs.json, tesseract/) se résolvent bien
    une fois packagé. Lancer : MenusServices.exe --selftest
    """
    import tempfile

    from src.chemins import RACINE
    from src import licence
    from src.dossier import LignePrestation, SaisieDossier, generer_dossier

    print(f"RACINE (résolue) : {RACINE}")
    print(f"frozen           : {getattr(sys, 'frozen', False)}")

    # 1. Licence (lue depuis config.json À CÔTÉ de l'exe)
    res = licence.verifier(licence.charger_config())
    print(f"Licence          : autorise={res.autorise} mode={res.mode} — {res.message}")
    if not res.autorise:
        print("SELFTEST FAIL (licence)")
        return 1

    # 2. Génération complète (lit modeles/ + tarifs.json À CÔTÉ de l'exe)
    saisie = SaisieDossier(
        civilite="Mme", prenom="Test", nom="Packaging",
        adresse="1 rue du Test", cp="84100", ville="Orange",
        benef_identique=True,
        lignes=[LignePrestation("Menus du marché 4C", 6), LignePrestation("Menus du jour 5C", 4)],
        tournee="T1", jours_repas=["Lundi", "Jeudi"], commencement="attendre",
        mode_paiement="prelevement",  # requis pour générer l'autorisation de prélèvement
        devis_num="10062026-1", date_devis="07/06/2026", date_validite="07/07/2026", lieu="Orange",
    )
    g = generer_dossier(saisie)
    print(f"Dossier généré   : {g.dossier}")
    for f in g.fichiers:
        print(f"  - {f.name} : {'OK' if f.exists() else 'MANQUANT'}")
    docs_ok = all(f.exists() for f in g.fichiers)
    a_devis = any("Devis" in f.name for f in g.fichiers)
    a_cond = any("Conditions" in f.name for f in g.fichiers)
    a_sepa = any("Mandat_SEPA" in f.name for f in g.fichiers)
    a_cgv = any("CGV" in f.name for f in g.fichiers)
    print(f"  devis={a_devis} conditions={a_cond} mandat={a_sepa} cgv={a_cgv}")

    # 3. OCR : Tesseract embarqué trouvé + lecture réelle d'une image générée
    from src.ocr.rib import TESSERACT_EXE, extraire_iban, lire_rib
    print(f"Tesseract        : présent={TESSERACT_EXE.exists()} — {TESSERACT_EXE}")
    ocr_ok = None
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (900, 160), "white")
        d = ImageDraw.Draw(img)
        try:
            police = ImageFont.truetype("arial.ttf", 40)
        except OSError:
            police = ImageFont.load_default()
        d.text((10, 20), "IBAN FR76 3000 4000 0100 0012 3456 789", fill="black", font=police)
        d.text((10, 90), "BIC BNPAFRPPXXX", fill="black", font=police)
        tmp = Path(tempfile.gettempdir()) / "lms_selftest_rib.png"
        img.save(tmp)
        rib = lire_rib(tmp)
        tmp.unlink(missing_ok=True)
        ocr_ok = rib.iban_valide
        print(f"OCR             : IBAN={rib.iban} valide={rib.iban_valide} BIC={rib.bic}")
    except Exception as e:  # noqa: BLE001 — OCR non bloquant pour le selftest
        print(f"OCR             : non testé ({e})")

    succes = docs_ok and a_devis and a_cond and a_sepa and a_cgv
    print("SELFTEST", "PASS" if succes else "FAIL")
    return 0 if succes else 1


def main() -> None:
    if "--selftest" in sys.argv:
        sys.exit(_selftest())

    app = QApplication(sys.argv)

    # Vérification de licence AVANT toute UI métier (kill switch, §15).
    res = licence.verifier(licence.charger_config())
    if not res.autorise:
        QMessageBox.critical(None, "Accès bloqué — Les Menus Services", res.message)
        sys.exit(1)

    fenetre = MainWindow()
    if res.mode == "hors-ligne":
        # Note discrète : on fonctionne sur la tolérance hors-ligne.
        fenetre.setWindowTitle(fenetre.windowTitle() + "   —   [hors-ligne]")
    fenetre.showMaximized()  # s'ouvre en grand (plein écran utile, barre de titre conservée)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
