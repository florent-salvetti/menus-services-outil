"""Widget de saisie des prestations : lignes dynamiques (formule + nb repas)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.dossier import LignePrestation


class _LigneWidget(QWidget):
    """Une ligne : formule (liste déroulante) + nb repas/sem + supprimer."""

    modifie = Signal()
    supprimee = Signal(object)

    def __init__(self, formules: list[str]):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self.combo = QComboBox()
        self.combo.addItems(formules)
        self.combo.setMinimumWidth(320)
        self.combo.currentIndexChanged.connect(self.modifie)

        self.spin = QSpinBox()
        self.spin.setRange(0, 99)
        self.spin.setValue(0)
        self.spin.valueChanged.connect(self.modifie)

        btn = QPushButton("✕")
        btn.setFixedWidth(32)
        btn.setToolTip("Supprimer cette ligne")
        btn.clicked.connect(lambda: self.supprimee.emit(self))

        lay.addWidget(self.combo, 1)
        lay.addWidget(QLabel("× "))
        lay.addWidget(self.spin)
        lay.addWidget(QLabel("repas/sem."))
        lay.addWidget(btn)

    def ligne(self) -> LignePrestation:
        return LignePrestation(self.combo.currentText(), self.spin.value())


class PrestationsWidget(QWidget):
    """Liste dynamique de prestations + bouton « ajouter une formule »."""

    modifie = Signal()

    def __init__(self, formules: list[str]):
        super().__init__()
        self._formules = formules
        self._lignes: list[_LigneWidget] = []

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self._conteneur = QVBoxLayout()
        self._layout.addLayout(self._conteneur)

        ajouter = QPushButton("➕  Ajouter une formule")
        ajouter.clicked.connect(lambda: self.ajouter_ligne())
        self._layout.addWidget(ajouter)

        self.ajouter_ligne()  # une ligne au démarrage

    def ajouter_ligne(self) -> None:
        ligne = _LigneWidget(self._formules)
        ligne.modifie.connect(self.modifie)
        ligne.supprimee.connect(self._supprimer)
        self._lignes.append(ligne)
        self._conteneur.addWidget(ligne)
        self.modifie.emit()

    def _supprimer(self, ligne: _LigneWidget) -> None:
        if len(self._lignes) <= 1:
            return  # on garde toujours au moins une ligne
        self._lignes.remove(ligne)
        ligne.setParent(None)
        ligne.deleteLater()
        self.modifie.emit()

    def lignes(self) -> list[LignePrestation]:
        """Lignes valides (formule choisie + quantité > 0)."""
        return [l.ligne() for l in self._lignes if l.spin.value() > 0]
