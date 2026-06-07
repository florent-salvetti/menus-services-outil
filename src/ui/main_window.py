"""Fenêtre principale : formulaire de saisie unique relié aux générateurs.

L'UI ne fait QU'appeler l'existant : src.dossier (orchestration) + src.calcul
(aperçu) + src.iban (validation IBAN). Aucune logique métier ici.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.calcul import charger_grille, fmt_eur
from src.documents.conditions import JOURS
from src.dossier import GRILLE, SaisieDossier, calculer_saisie, generer_dossier
from src import compteur
from src.iban import formater_affichage, iban_valide, normaliser
from src.ui.dialog_recap import DialogRecap
from src.ui.prestations_widget import PrestationsWidget


def _section(titre: str) -> tuple[QGroupBox, QGridLayout]:
    box = QGroupBox(titre)
    grid = QGridLayout(box)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(6)
    return box, grid


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Générateur de documents — Les Menus Services Orange")
        self.resize(900, 760)

        self._formules = list(charger_grille(GRILLE).keys())

        racine = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        racine.addWidget(scroll, 1)

        contenu = QWidget()
        scroll.setWidget(contenu)
        self._form = QVBoxLayout(contenu)

        self._build_client()
        self._build_beneficiaire()
        self._build_prestations()
        self._build_livraison()
        self._build_banque()
        self._build_devis()
        self._build_barre(racine)

        self._maj_apercu()
        self._maj_etat()

    # ----------------------------------------------------------------- client
    def _build_client(self) -> None:
        box, g = _section("Client / payeur")
        self.civilite = QLineEdit("Mme")
        self.civilite.setFixedWidth(60)
        self.prenom = QLineEdit()
        self.nom = QLineEdit()
        self.adresse = QLineEdit()
        self.cp = QLineEdit()
        self.cp.setFixedWidth(80)
        self.ville = QLineEdit()
        self.tel = QLineEdit()
        self.email = QLineEdit()

        g.addWidget(QLabel("Civilité"), 0, 0)
        g.addWidget(self.civilite, 0, 1)
        g.addWidget(QLabel("Prénom"), 0, 2)
        g.addWidget(self.prenom, 0, 3)
        g.addWidget(QLabel("NOM"), 0, 4)
        g.addWidget(self.nom, 0, 5)
        g.addWidget(QLabel("Adresse"), 1, 0)
        g.addWidget(self.adresse, 1, 1, 1, 5)
        g.addWidget(QLabel("CP"), 2, 0)
        g.addWidget(self.cp, 2, 1)
        g.addWidget(QLabel("Ville"), 2, 2)
        g.addWidget(self.ville, 2, 3)
        g.addWidget(QLabel("Tél"), 3, 0)
        g.addWidget(self.tel, 3, 1)
        g.addWidget(QLabel("Email"), 3, 2)
        g.addWidget(self.email, 3, 3, 1, 3)

        self.nom.textChanged.connect(self._maj_etat)
        self._form.addWidget(box)

    # ----------------------------------------------------------- bénéficiaire
    def _build_beneficiaire(self) -> None:
        box, g = _section("Bénéficiaire des prestations (si différent du client)")
        self.benef_identique = QCheckBox("Identique au client")
        self.benef_identique.setChecked(True)
        self.benef_identique.stateChanged.connect(self._toggle_benef)

        self.benef_prenom = QLineEdit()
        self.benef_nom = QLineEdit()
        self.benef_adresse = QLineEdit()
        self.lieu_prestation = QLineEdit()
        self.lieu_prestation.setPlaceholderText("si différent de l'adresse du bénéficiaire")

        g.addWidget(self.benef_identique, 0, 0, 1, 4)
        g.addWidget(QLabel("Prénom"), 1, 0)
        g.addWidget(self.benef_prenom, 1, 1)
        g.addWidget(QLabel("NOM"), 1, 2)
        g.addWidget(self.benef_nom, 1, 3)
        g.addWidget(QLabel("Adresse bénéficiaire"), 2, 0)
        g.addWidget(self.benef_adresse, 2, 1, 1, 3)
        g.addWidget(QLabel("Lieu de prestation"), 3, 0)
        g.addWidget(self.lieu_prestation, 3, 1, 1, 3)

        self._benef_champs = [
            self.benef_prenom, self.benef_nom, self.benef_adresse, self.lieu_prestation,
        ]
        self._toggle_benef()
        self._form.addWidget(box)

    def _toggle_benef(self) -> None:
        actif = not self.benef_identique.isChecked()
        for w in self._benef_champs:
            w.setEnabled(actif)
            if not actif:
                w.clear()

    # ------------------------------------------------------------ prestations
    def _build_prestations(self) -> None:
        box = QGroupBox("Prestations")
        lay = QVBoxLayout(box)
        self.prestations = PrestationsWidget(self._formules)
        self.prestations.modifie.connect(self._maj_apercu)
        self.prestations.modifie.connect(self._maj_etat)
        lay.addWidget(self.prestations)
        self._form.addWidget(box)

    # -------------------------------------------------------------- livraison
    def _build_livraison(self) -> None:
        box, g = _section("Livraison")
        self.tournee_t1 = QRadioButton("T1 — Lundi / Jeudi")
        self.tournee_t2 = QRadioButton("T2 — Mardi / Vendredi")
        self.tournee_t1.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self.tournee_t1)
        grp.addButton(self.tournee_t2)
        ligne_t = QHBoxLayout()
        ligne_t.addWidget(self.tournee_t1)
        ligne_t.addWidget(self.tournee_t2)
        ligne_t.addStretch()

        self.jours = {}
        ligne_j = QHBoxLayout()
        for j in JOURS:
            cb = QCheckBox(j)
            self.jours[j] = cb
            ligne_j.addWidget(cb)
        ligne_j.addStretch()

        self.comm_attendre = QRadioButton("Attendre le délai de 14 j")
        self.comm_avant = QRadioButton("Démarrer avant la fin du délai")
        self.comm_attendre.setChecked(True)
        grp2 = QButtonGroup(self)
        grp2.addButton(self.comm_attendre)
        grp2.addButton(self.comm_avant)
        self.date_premiere = QLineEdit()
        self.date_premiere.setPlaceholderText("jj/mm/aaaa")
        self.date_premiere.setFixedWidth(110)
        ligne_c = QHBoxLayout()
        ligne_c.addWidget(self.comm_attendre)
        ligne_c.addWidget(self.comm_avant)
        ligne_c.addWidget(QLabel("1re livraison"))
        ligne_c.addWidget(self.date_premiere)
        ligne_c.addStretch()

        g.addWidget(QLabel("Tournée"), 0, 0)
        g.addLayout(ligne_t, 0, 1)
        g.addWidget(QLabel("Jours de repas"), 1, 0)
        g.addLayout(ligne_j, 1, 1)
        g.addWidget(QLabel("Commencement"), 2, 0)
        g.addLayout(ligne_c, 2, 1)
        self._form.addWidget(box)

    # ----------------------------------------------------------------- banque
    def _build_banque(self) -> None:
        box, g = _section("Banque (mandat SEPA) — IBAN/BIC non conservés (RGPD)")
        self.banque_nom = QLineEdit()
        self.banque_adresse = QLineEdit()
        self.iban = QLineEdit()
        self.iban.setPlaceholderText("FR76 ...")
        self.bic = QLineEdit()
        self.iban_etat = QLabel("")
        self.iban.textChanged.connect(self._maj_iban)

        g.addWidget(QLabel("Établissement"), 0, 0)
        g.addWidget(self.banque_nom, 0, 1)
        g.addWidget(QLabel("Adresse banque"), 0, 2)
        g.addWidget(self.banque_adresse, 0, 3)
        self.bouton_rib = QPushButton("📷  Lire un RIB scanné…")
        self.bouton_rib.setToolTip(
            "Pré-remplit IBAN/BIC depuis un RIB (image ou PDF). "
            "Le fichier n'est ni copié ni supprimé ; à vérifier avant usage."
        )
        self.bouton_rib.clicked.connect(self._lire_rib)

        g.addWidget(QLabel("IBAN"), 1, 0)
        g.addWidget(self.iban, 1, 1, 1, 2)
        g.addWidget(self.iban_etat, 1, 3)
        g.addWidget(QLabel("BIC"), 2, 0)
        g.addWidget(self.bic, 2, 1)
        g.addWidget(self.bouton_rib, 2, 2, 1, 2)
        self._form.addWidget(box)

    def _lire_rib(self) -> None:
        """Ouvre un RIB (image/PDF), pré-remplit IBAN/BIC. Validation humaine.

        Le fichier source est seulement LU (en mémoire) : ni copié, ni supprimé.
        """
        chemin, _ = QFileDialog.getOpenFileName(
            self, "Choisir un RIB scanné", "",
            "RIB (*.pdf *.png *.jpg *.jpeg *.tif *.tiff *.bmp)",
        )
        if not chemin:
            return

        from src.ocr.rib import lire_rib  # import paresseux (Tesseract requis ici)

        try:
            res = lire_rib(chemin)
        except FileNotFoundError as e:
            QMessageBox.warning(self, "Tesseract introuvable", str(e))
            return
        except Exception as e:  # noqa: BLE001 — lecture OCR robuste
            QMessageBox.warning(self, "Lecture du RIB impossible", str(e))
            return

        if res.iban:
            self.iban.setText(formater_affichage(res.iban))  # déclenche ✓/✗
        if res.bic:
            self.bic.setText(res.bic)

        if not res.iban:
            QMessageBox.information(
                self, "RIB lu",
                "Aucun IBAN reconnu : saisie manuelle nécessaire.\n"
                "(Vérifiez la qualité du scan.)",
            )
        elif not res.iban_valide:
            QMessageBox.warning(
                self, "IBAN à vérifier",
                "IBAN reconnu mais clé mod 97 invalide → lecture probablement "
                "imparfaite.\nComparez au RIB et corrigez avant de générer.",
            )

    def _maj_iban(self) -> None:
        txt = normaliser(self.iban.text())
        if not txt:
            self.iban_etat.setText("")
        elif iban_valide(txt):
            self.iban_etat.setText("✓ IBAN valide")
            self.iban_etat.setStyleSheet("color: green;")
        else:
            self.iban_etat.setText("✗ IBAN invalide (mod 97)")
            self.iban_etat.setStyleSheet("color: #c0392b;")
        self._maj_etat()

    # ------------------------------------------------------------------ devis
    def _build_devis(self) -> None:
        box, g = _section("Devis")
        aujourdhui = date.today()
        self.devis_num = QLineEdit(compteur.numero_propose())
        self.date_devis = QLineEdit(aujourdhui.strftime("%d/%m/%Y"))
        self.date_validite = QLineEdit((aujourdhui + timedelta(days=30)).strftime("%d/%m/%Y"))
        self.lieu = QLineEdit("Orange")
        g.addWidget(QLabel("N° devis"), 0, 0)
        g.addWidget(self.devis_num, 0, 1)
        g.addWidget(QLabel("Date"), 0, 2)
        g.addWidget(self.date_devis, 0, 3)
        g.addWidget(QLabel("Validité"), 0, 4)
        g.addWidget(self.date_validite, 0, 5)
        g.addWidget(QLabel("Fait à"), 1, 0)
        g.addWidget(self.lieu, 1, 1)
        self._form.addWidget(box)

    # ------------------------------------------------------------- barre bas
    def _build_barre(self, racine: QVBoxLayout) -> None:
        barre = QFrame()
        barre.setFrameShape(QFrame.StyledPanel)
        lay = QVBoxLayout(barre)

        self.apercu = QLabel("Aperçu : —")
        self.apercu.setStyleSheet("font-weight: bold;")
        self.statut = QLabel("")
        self.sepa_note = QLabel("")

        ligne = QHBoxLayout()
        infos = QVBoxLayout()
        infos.addWidget(self.apercu)
        infos.addWidget(self.statut)
        infos.addWidget(self.sepa_note)
        ligne.addLayout(infos, 1)

        self.bouton = QPushButton("Générer les documents")
        self.bouton.setMinimumHeight(44)
        self.bouton.clicked.connect(self._generer)
        ligne.addWidget(self.bouton)

        lay.addLayout(ligne)
        racine.addWidget(barre)

    # --------------------------------------------------------------- collecte
    def _collecter(self) -> SaisieDossier:
        return SaisieDossier(
            civilite=self.civilite.text(), prenom=self.prenom.text(), nom=self.nom.text(),
            adresse=self.adresse.text(), cp=self.cp.text(), ville=self.ville.text(),
            tel=self.tel.text(), email=self.email.text(),
            benef_identique=self.benef_identique.isChecked(),
            benef_prenom=self.benef_prenom.text(), benef_nom=self.benef_nom.text(),
            benef_adresse=self.benef_adresse.text(),
            lieu_prestation=self.lieu_prestation.text(),
            lignes=self.prestations.lignes(),
            tournee="T1" if self.tournee_t1.isChecked() else "T2",
            jours_repas=[j for j, cb in self.jours.items() if cb.isChecked()],
            commencement="attendre" if self.comm_attendre.isChecked() else "avant",
            date_premiere_livraison=self.date_premiere.text(),
            banque_nom=self.banque_nom.text(), banque_adresse=self.banque_adresse.text(),
            iban=self.iban.text(), bic=self.bic.text(),
            devis_num=self.devis_num.text(), date_devis=self.date_devis.text(),
            date_validite=self.date_validite.text(), lieu=self.lieu.text(),
        )

    # ----------------------------------------------------------------- aperçu
    def _maj_apercu(self) -> None:
        res = calculer_saisie(self._collecter())
        if res is None:
            self.apercu.setText("Aperçu :  —  (aucune formule saisie)")
            return
        self.apercu.setText(
            f"Aperçu :  Hebdo {fmt_eur(res.total_hebdo_ttc)} TTC  ·  "
            f"Mensuel {fmt_eur(res.cout_mensuel_ttc)}  ·  "
            f"Reste à charge {fmt_eur(res.total_apres_ci)}"
        )

    def _maj_etat(self) -> None:
        manques = []
        if not self.nom.text().strip():
            manques.append("nom du client")
        if not self.prestations.lignes():
            manques.append("au moins une formule")
        self.bouton.setEnabled(not manques)
        self.statut.setText("Prêt à générer." if not manques else "Manque : " + ", ".join(manques))

        iban = normaliser(self.iban.text())
        if not iban:
            self.sepa_note.setText("Mandat SEPA : pas d'IBAN → non généré.")
            self.sepa_note.setStyleSheet("color: #555;")
        elif iban_valide(iban):
            self.sepa_note.setText("Mandat SEPA : IBAN valide ✓ → sera généré.")
            self.sepa_note.setStyleSheet("color: green;")
        else:
            self.sepa_note.setText("Mandat SEPA : IBAN invalide ✗ → non généré.")
            self.sepa_note.setStyleSheet("color: #c0392b;")

    # -------------------------------------------------------------- génération
    def _generer(self) -> None:
        try:
            res = generer_dossier(self._collecter())
        except Exception as e:  # noqa: BLE001 — on remonte l'erreur à l'UI
            QMessageBox.critical(self, "Erreur de génération", str(e))
            return

        # Numéro de devis suivant pour le prochain dossier.
        self.devis_num.setText(compteur.numero_propose())

        # Ouvre le dossier dans l'explorateur, puis le récap copiable + impression.
        self._ouvrir_dossier(res.dossier)
        DialogRecap(self, res).exec()

    @staticmethod
    def _ouvrir_dossier(chemin: Path) -> None:
        try:
            os.startfile(str(chemin))  # Windows : ouvre l'explorateur
        except Exception:  # noqa: BLE001 — non bloquant si indisponible
            pass
