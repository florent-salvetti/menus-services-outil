"""Éditeur de la liste des régimes particuliers (regimes.json).

Ajouter / renommer (double-clic) / supprimer / réordonner les régimes proposés
dans les lignes de prestation. Aucune incidence tarifaire : le libellé est
simplement reporté au bout du nom de la prestation sur les documents.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from src import regimes


class DialogRegimes(QDialog):
    """Liste éditable des régimes, enregistrée dans regimes.json."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Éditer les régimes")
        self.resize(420, 460)
        self.setModal(True)

        lay = QVBoxLayout(self)

        intro = QLabel(
            "Régimes proposés sur les lignes de prestation. Double-cliquez sur un "
            "régime pour le renommer, faites-le glisser pour réordonner. Le régime "
            "est un libellé ajouté au nom de la prestation (sans effet sur le tarif)."
        )
        intro.setWordWrap(True)
        lay.addWidget(intro)

        self.liste = QListWidget()
        self.liste.setDragDropMode(QAbstractItemView.InternalMove)
        for r in regimes.charger_regimes():
            self._ajouter_item(r)
        lay.addWidget(self.liste, 1)

        barre = QHBoxLayout()
        btn_ajout = QPushButton("➕  Ajouter un régime")
        btn_ajout.setObjectName("boutonAjouter")
        btn_ajout.clicked.connect(self._ajouter)
        btn_suppr = QPushButton("Supprimer")
        btn_suppr.clicked.connect(self._supprimer)
        barre.addWidget(btn_ajout)
        barre.addWidget(btn_suppr)
        barre.addStretch()
        lay.addLayout(barre)

        boutons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        boutons.button(QDialogButtonBox.Save).setText("Enregistrer")
        boutons.button(QDialogButtonBox.Save).setObjectName("boutonPrincipal")
        boutons.button(QDialogButtonBox.Cancel).setText("Annuler")
        boutons.accepted.connect(self._enregistrer)
        boutons.rejected.connect(self.reject)
        lay.addWidget(boutons)

    # ------------------------------------------------------------------ items
    def _ajouter_item(self, texte: str) -> QListWidgetItem:
        item = QListWidgetItem(texte)
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self.liste.addItem(item)
        return item

    def _ajouter(self) -> None:
        item = self._ajouter_item("nouveau régime")
        self.liste.setCurrentItem(item)
        self.liste.editItem(item)  # édition immédiate du libellé

    def _supprimer(self) -> None:
        r = self.liste.currentRow()
        if r < 0:
            QMessageBox.information(self, "Régimes", "Sélectionnez d'abord un régime à supprimer.")
            return
        nom = self.liste.item(r).text().strip()
        if QMessageBox.question(
            self, "Supprimer le régime", f"Supprimer « {nom or '(sans nom)'} » ?"
        ) == QMessageBox.Yes:
            self.liste.takeItem(r)

    # ----------------------------------------------------------- enregistrement
    def _enregistrer(self) -> None:
        valeurs = [self.liste.item(i).text() for i in range(self.liste.count())]
        try:
            regimes.enregistrer_regimes(valeurs)
        except ValueError as e:
            QMessageBox.warning(self, "Saisie invalide", str(e))
            return
        self.accept()
