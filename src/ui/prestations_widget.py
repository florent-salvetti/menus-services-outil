"""Widget de saisie des prestations : lignes dynamiques (formule + nb repas)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.dossier import LignePrestation


#: Régimes particuliers proposés (sans incidence tarifaire). Le libellé est
#: reporté tel quel au bout du nom de la prestation sur devis + conditions.
REGIMES = ["diabétique", "sans sel", "mixé"]


class _LigneWidget(QWidget):
    """Une ligne : formule + nb repas/sem + régime particulier + supprimer."""

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

        # Régime particulier : case + choix (actif uniquement si cochée).
        self.regime_actif = QCheckBox("Régime")
        self.regime_actif.setToolTip("Régime particulier, indiqué au bout du nom de la prestation")
        self.regime_actif.stateChanged.connect(self._toggle_regime)
        self.regime = QComboBox()
        self.regime.addItems(REGIMES)
        self.regime.setVisible(False)  # masqué tant que la case n'est pas cochée
        self.regime.currentIndexChanged.connect(self.modifie)

        btn = QPushButton("✕")
        btn.setObjectName("boutonSuppr")
        btn.setFixedSize(28, 28)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip("Supprimer cette ligne")
        btn.clicked.connect(lambda: self.supprimee.emit(self))

        lay.setSpacing(8)
        lay.addWidget(self.combo, 1)
        lay.addWidget(QLabel("×"))
        lay.addWidget(self.spin)
        lay.addWidget(QLabel("repas/sem."))
        lay.addWidget(self.regime_actif)
        lay.addWidget(self.regime)
        lay.addWidget(btn)

    def _toggle_regime(self) -> None:
        self.regime.setVisible(self.regime_actif.isChecked())
        self.modifie.emit()

    def ligne(self) -> LignePrestation:
        regime = self.regime.currentText() if self.regime_actif.isChecked() else ""
        return LignePrestation(self.combo.currentText(), self.spin.value(), regime=regime)

    def recharger_formules(self, formules: list[str]) -> None:
        """Met à jour la liste des formules en gardant la sélection si possible."""
        choix = self.combo.currentText()
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItems(formules)
        if choix in formules:
            self.combo.setCurrentText(choix)
        self.combo.blockSignals(False)


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
        ajouter.setObjectName("boutonAjouter")
        ajouter.setCursor(Qt.PointingHandCursor)
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

    def recharger_formules(self, formules: list[str]) -> None:
        """Propage une nouvelle grille : lignes existantes + futurs ajouts."""
        self._formules = formules
        for ligne in self._lignes:
            ligne.recharger_formules(formules)
