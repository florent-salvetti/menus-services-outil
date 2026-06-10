"""Éditeur de la grille tarifaire (tarifs.json).

Permet à l'agence de mettre à jour les tarifs SANS éditer le JSON à la main
(CLAUDE.md §5 : la grille est une donnée remplaçable, jamais codée en dur).

Garde-fous :
- sauvegarde de l'ancienne grille en `tarifs.json.bak` avant d'écrire (rollback) ;
- le fichier écrit est RELU via `charger_grille` avant d'être validé : une grille
  corrompue ne remplace jamais une grille saine ;
- la catégorie (repas / supplément / service) pilote le décompte « repas » du
  devis (cf. src.calcul.Formule.est_repas).
"""

from __future__ import annotations

import json
from collections import OrderedDict
from decimal import Decimal, InvalidOperation
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QDialog,
)

from src.calcul import charger_grille
from src.dossier import GRILLE

#: Colonnes : (clé JSON, en-tête affiché, numérique ?). L'ordre définit aussi
#: l'ordre des clés dans le fichier écrit.
_COLONNES = [
    ("formule", "Formule", False),
    ("categorie", "Catégorie", False),  # rendu via combo, pas un champ texte
    ("ttc", "TTC", True),
    ("ht", "HT", True),
    ("apres_ci", "Après CI", True),
    ("service_ttc", "Service TTC", True),
    ("service_ht", "Service HT", True),
    ("repas_ttc", "Repas TTC", True),
    ("repas_ht", "Repas HT", True),
]
_CATEGORIES = ["repas", "supplement", "service"]


def _fmt(valeur) -> str:
    """Affiche un nombre à la française (virgule), vide si None."""
    if valeur is None:
        return ""
    s = str(valeur)
    return s.replace(".", ",")


def _parse(texte: str):
    """Convertit la saisie en float (None si vide). Accepte virgule ou point.

    Lève ValueError si le texte n'est pas un nombre valide.
    """
    t = texte.strip().replace(" ", "").replace(",", ".")
    if t == "":
        return None
    try:
        return float(Decimal(t))
    except (InvalidOperation, ValueError):
        raise ValueError(texte)


class DialogTarifs(QDialog):
    """Tableau éditable de la grille tarifaire, enregistré dans tarifs.json."""

    def __init__(self, parent=None, chemin: Path = GRILLE):
        super().__init__(parent)
        self._chemin = Path(chemin)
        self.setWindowTitle("Éditer les tarifs")
        self.resize(960, 600)
        self.setModal(True)

        lay = QVBoxLayout(self)

        intro = QLabel(
            "Modifiez les tarifs publics (TTC / HT), la décomposition repas / service, "
            "le tarif après crédit d'impôt et la catégorie de chaque ligne. "
            "Laissez une case vide pour « non applicable ». La catégorie « repas » est "
            "la seule comptée dans le « Nombre de repas » du devis."
        )
        intro.setWordWrap(True)
        lay.addWidget(intro)

        self.table = QTableWidget(0, len(_COLONNES))
        self.table.setHorizontalHeaderLabels([h for _, h, _ in _COLONNES])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, len(_COLONNES)):
            self.table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        lay.addWidget(self.table, 1)

        # Boutons d'édition de lignes
        barre = QHBoxLayout()
        btn_ajout = QPushButton("➕  Ajouter une ligne")
        btn_ajout.setObjectName("boutonAjouter")
        btn_ajout.clicked.connect(lambda: self._ajouter_ligne())
        btn_suppr = QPushButton("Supprimer la ligne sélectionnée")
        btn_suppr.clicked.connect(self._supprimer_ligne)
        barre.addWidget(btn_ajout)
        barre.addWidget(btn_suppr)
        barre.addStretch()
        lay.addLayout(barre)

        # Enregistrer / Annuler
        boutons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        boutons.button(QDialogButtonBox.Save).setText("Enregistrer")
        boutons.button(QDialogButtonBox.Save).setObjectName("boutonPrincipal")
        boutons.button(QDialogButtonBox.Cancel).setText("Annuler")
        boutons.accepted.connect(self._enregistrer)
        boutons.rejected.connect(self.reject)
        lay.addWidget(boutons)

        self._charger()

    # ------------------------------------------------------------- chargement
    def _charger(self) -> None:
        data = json.loads(self._chemin.read_text(encoding="utf-8-sig"))
        for entree in data:
            self._ajouter_ligne(entree)

    def _ajouter_ligne(self, entree: dict | None = None) -> None:
        entree = entree or {}
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c, (cle, _, numerique) in enumerate(_COLONNES):
            if cle == "categorie":
                combo = QComboBox()
                combo.addItems(_CATEGORIES)
                cat = entree.get("categorie", "repas")
                if cat in _CATEGORIES:
                    combo.setCurrentText(cat)
                self.table.setCellWidget(r, c, combo)
            else:
                valeur = entree.get(cle)
                texte = _fmt(valeur) if numerique else (valeur or "")
                item = QTableWidgetItem(texte)
                if numerique:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r, c, item)

    def _supprimer_ligne(self) -> None:
        r = self.table.currentRow()
        if r < 0:
            QMessageBox.information(self, "Tarifs", "Sélectionnez d'abord une ligne à supprimer.")
            return
        nom = self.table.item(r, 0).text().strip() if self.table.item(r, 0) else ""
        if QMessageBox.question(
            self, "Supprimer la ligne",
            f"Supprimer la formule « {nom or '(sans nom)'} » ?",
        ) == QMessageBox.Yes:
            self.table.removeRow(r)

    # ------------------------------------------------------------ enregistrement
    def _collecter(self) -> list[OrderedDict]:
        """Lit le tableau → liste de dicts ; lève ValueError si saisie invalide."""
        out: list[OrderedDict] = []
        noms_vus: set[str] = set()
        for r in range(self.table.rowCount()):
            nom_item = self.table.item(r, 0)
            nom = (nom_item.text().strip() if nom_item else "")
            if not nom:
                raise ValueError(f"Ligne {r + 1} : le nom de la formule est obligatoire.")
            if nom in noms_vus:
                raise ValueError(f"Formule en double : « {nom} ».")
            noms_vus.add(nom)

            d: OrderedDict = OrderedDict()
            for c, (cle, entete, numerique) in enumerate(_COLONNES):
                if cle == "formule":
                    d[cle] = nom
                elif cle == "categorie":
                    d[cle] = self.table.cellWidget(r, c).currentText()
                else:
                    item = self.table.item(r, c)
                    texte = item.text() if item else ""
                    try:
                        d[cle] = _parse(texte)
                    except ValueError:
                        raise ValueError(
                            f"Ligne {r + 1} (« {nom} »), colonne « {entete} » : "
                            f"« {texte.strip()} » n'est pas un nombre valide."
                        )
            if d.get("ttc") is None or d.get("ht") is None:
                raise ValueError(f"« {nom} » : les colonnes TTC et HT sont obligatoires.")
            out.append(d)
        if not out:
            raise ValueError("La grille ne peut pas être vide.")
        return out

    def _incoherences(self, data: list[OrderedDict]) -> list[str]:
        """Repère les lignes où repas + service ≠ TTC (à l'arrondi près)."""
        alertes = []
        for d in data:
            r_ttc, s_ttc, ttc = d.get("repas_ttc"), d.get("service_ttc"), d.get("ttc")
            if r_ttc is not None and s_ttc is not None and ttc is not None:
                if abs((r_ttc + s_ttc) - ttc) > 0.01:
                    alertes.append(
                        f"• {d['formule']} : repas {_fmt(r_ttc)} + service {_fmt(s_ttc)} "
                        f"≠ TTC {_fmt(ttc)}"
                    )
        return alertes

    def _enregistrer(self) -> None:
        try:
            data = self._collecter()
        except ValueError as e:
            QMessageBox.warning(self, "Saisie invalide", str(e))
            return

        alertes = self._incoherences(data)
        if alertes:
            msg = (
                "Des décompositions repas + service ne correspondent pas au TTC :\n\n"
                + "\n".join(alertes)
                + "\n\nEnregistrer quand même ?"
            )
            if QMessageBox.question(self, "Incohérences détectées", msg) != QMessageBox.Yes:
                return

        # Sauvegarde de l'ancienne grille (rollback manuel possible).
        backup = None
        if self._chemin.exists():
            backup = self._chemin.with_suffix(self._chemin.suffix + ".bak")
            backup.write_text(self._chemin.read_text(encoding="utf-8-sig"), encoding="utf-8")

        contenu = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        self._chemin.write_text(contenu, encoding="utf-8")

        # Relecture de contrôle : une grille corrompue ne doit pas rester en place.
        try:
            charger_grille(self._chemin)
        except Exception as e:  # noqa: BLE001
            if backup is not None:
                self._chemin.write_text(backup.read_text(encoding="utf-8-sig"), encoding="utf-8")
            QMessageBox.critical(
                self, "Erreur",
                f"La grille enregistrée est invalide, l'ancienne a été restaurée.\n\n{e}",
            )
            return

        QMessageBox.information(
            self, "Tarifs enregistrés",
            "La grille tarifaire a été mise à jour."
            + (f"\nSauvegarde de l'ancienne : {backup.name}" if backup else ""),
        )
        self.accept()
