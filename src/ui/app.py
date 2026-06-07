"""Point d'entrée de l'interface.

Lancer depuis la racine du projet :
    python -m src.ui.app
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permet `python -m src.ui.app` ET `python src/ui/app.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    fenetre = MainWindow()
    fenetre.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
