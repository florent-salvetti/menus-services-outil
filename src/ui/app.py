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


def main() -> None:
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
    fenetre.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
