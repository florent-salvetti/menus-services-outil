"""Dialogue post-génération : récapitulatif copiable + impression groupée."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from src import impression
from src.dossier import ResultatGeneration


class DialogRecap(QDialog):
    """Affiche le récap (copiable) et propose l'impression du PDF fusionné."""

    def __init__(self, parent, res: ResultatGeneration):
        super().__init__(parent)
        self.res = res
        self.setWindowTitle("Dossier généré — récapitulatif")
        self.resize(660, 580)
        lay = QVBoxLayout(self)

        lay.addWidget(QLabel(f"Dossier : {res.dossier}"))

        self.zone = QPlainTextEdit(res.recap)
        self.zone.setReadOnly(True)
        police = QFont("Consolas")
        police.setStyleHint(QFont.Monospace)
        self.zone.setFont(police)
        lay.addWidget(self.zone, 1)

        fichiers = "\n".join(f"• {Path(p).name}" for p in res.fichiers)
        lay.addWidget(QLabel(f"Fichiers générés :\n{fichiers}"))
        if res.avertissements:
            av = QLabel("\n".join(f"⚠ {a}" for a in res.avertissements))
            av.setStyleSheet("color:#c0392b;")
            av.setWordWrap(True)
            lay.addWidget(av)

        self.feedback = QLabel("")
        self.feedback.setStyleSheet("color: green;")
        lay.addWidget(self.feedback)

        boutons = QHBoxLayout()
        b_copier = QPushButton("📋  Copier le récap (pour le CRM)")
        b_copier.clicked.connect(self._copier)
        self.b_imprimer = QPushButton("🖨  Imprimer le dossier complet (PDF)")
        self.b_imprimer.clicked.connect(self._imprimer)
        b_fermer = QPushButton("Fermer")
        b_fermer.clicked.connect(self.accept)
        boutons.addWidget(b_copier)
        boutons.addWidget(self.b_imprimer)
        boutons.addStretch()
        boutons.addWidget(b_fermer)
        lay.addLayout(boutons)

    def _copier(self) -> None:
        QApplication.clipboard().setText(self.res.recap)
        self.feedback.setText("Récapitulatif copié dans le presse-papier ✓")

    def _imprimer(self) -> None:
        self.b_imprimer.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            sortie = self.res.dossier / f"Dossier_complet_{self.res.dossier.name}.pdf"
            pdf = impression.pdf_dossier_complet(self.res.fichiers, sortie)
            impression.imprimer(pdf)
            self.feedback.setText(f"PDF fusionné créé et envoyé à l'impression : {pdf.name} ✓")
        except impression.ConversionImpossible as e:
            # Confort, jamais bloquant : les .docx sont déjà dans le dossier.
            QMessageBox.warning(
                self, "PDF fusionné non créé",
                f"{e}\n\nVous pouvez imprimer les .docx directement depuis le dossier.",
            )
        except Exception as e:  # noqa: BLE001 — on remonte proprement à l'UI
            QMessageBox.warning(
                self, "PDF fusionné non créé",
                f"Impression du PDF fusionné impossible : {e}\n\n"
                "Les documents .docx restent disponibles dans le dossier.",
            )
        finally:
            QApplication.restoreOverrideCursor()
            self.b_imprimer.setEnabled(True)
