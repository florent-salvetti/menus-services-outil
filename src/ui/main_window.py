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
    QComboBox,
    QDoubleSpinBox,
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
from src.ui.dialog_recap import DialogRecap
from src.ui.dialog_tarifs import DialogTarifs
from src.ui.prestations_widget import PrestationsWidget
from src.ui.style import appliquer_ombre, construire_bandeau, feuille_qss


def _section(titre: str) -> tuple[QGroupBox, QGridLayout]:
    box = QGroupBox(titre)
    appliquer_ombre(box)  # effet « carte »
    grid = QGridLayout(box)
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(9)
    return box, grid


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Générateur de documents — Les Menus Services Orange")
        self.resize(900, 760)

        self._formules = list(charger_grille(GRILLE).keys())

        # Habillage charte Les Menus Services (visuel uniquement).
        self.setStyleSheet(feuille_qss())

        racine = QVBoxLayout(self)
        racine.setContentsMargins(0, 0, 0, 0)
        racine.setSpacing(0)

        self.btn_tarifs = QPushButton("Éditer les tarifs")
        self.btn_tarifs.setObjectName("boutonHeader")
        self.btn_tarifs.setCursor(Qt.PointingHandCursor)
        self.btn_tarifs.clicked.connect(self._editer_tarifs)
        racine.addWidget(construire_bandeau([self.btn_tarifs]))  # bandeau logo + action

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        racine.addWidget(scroll, 1)

        # Page : colonne centrée à largeur lisible (l'app se lance maximisée ;
        # sans plafond, les champs s'étirent sur toute la largeur de l'écran).
        page = QWidget()
        page.setObjectName("page")
        scroll.setWidget(page)
        centrage = QHBoxLayout(page)
        centrage.setContentsMargins(0, 0, 0, 0)
        colonne = QWidget()
        colonne.setMaximumWidth(1010)
        centrage.addStretch(1)
        centrage.addWidget(colonne)
        centrage.addStretch(1)
        self._form = QVBoxLayout(colonne)
        self._form.setContentsMargins(24, 20, 24, 24)
        self._form.setSpacing(18)

        self._build_client()
        self._build_beneficiaire()
        self._build_prestations()
        self._build_livraison()
        self._build_paiement()
        self._build_devis()
        self._build_barre(racine)

        self._maj_apercu()
        self._maj_etat()

    # --------------------------------------------------------- édition tarifs
    def _editer_tarifs(self) -> None:
        """Ouvre l'éditeur de la grille ; recharge les formules si modifiée."""
        if DialogTarifs(self).exec():
            self._formules = list(charger_grille(GRILLE).keys())
            self.prestations.recharger_formules(self._formules)
            self._maj_apercu()
            self._maj_etat()

    # ----------------------------------------------------------------- client
    def _build_client(self) -> None:
        box, g = _section("Client / payeur")
        self.civilite = QComboBox()
        self.civilite.addItems(["Mme", "M."])
        self.civilite.setFixedWidth(104)
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

        # Tutelle : si coché, les documents mentionnent le représentant légal.
        self.tutelle = QCheckBox("Client sous tutelle")
        self.tutelle.stateChanged.connect(self._toggle_tutelle)
        self.tutelle_organisme = QLineEdit()
        self.tutelle_organisme.setPlaceholderText("organisme (ex. UDAF 84)")
        self.tuteur_prenom = QLineEdit()
        self.tuteur_nom = QLineEdit()
        g.addWidget(self.tutelle, 4, 0, 1, 2)
        g.addWidget(QLabel("Organisme"), 5, 0)
        g.addWidget(self.tutelle_organisme, 5, 1, 1, 3)
        g.addWidget(QLabel("Prénom tuteur"), 6, 0)
        g.addWidget(self.tuteur_prenom, 6, 1)
        g.addWidget(QLabel("NOM tuteur"), 6, 2)
        g.addWidget(self.tuteur_nom, 6, 3)
        self._tutelle_champs = [self.tutelle_organisme, self.tuteur_prenom, self.tuteur_nom]
        self._toggle_tutelle()

        self.nom.textChanged.connect(self._maj_etat)
        self._form.addWidget(box)

    def _toggle_tutelle(self) -> None:
        actif = self.tutelle.isChecked()
        for w in self._tutelle_champs:
            w.setEnabled(actif)
            if not actif:
                w.clear()

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
        appliquer_ombre(box)  # effet « carte »
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
        ligne_t.setSpacing(20)
        ligne_t.addWidget(self.tournee_t1)
        ligne_t.addWidget(self.tournee_t2)
        ligne_t.addStretch()

        self.jours = {}
        ligne_j = QHBoxLayout()
        ligne_j.setSpacing(16)
        for j in JOURS:
            cb = QCheckBox(j)
            self.jours[j] = cb
            ligne_j.addWidget(cb)
        ligne_j.addStretch()

        self.comm_attendre = QRadioButton("Attendre le délai de 14 j")
        self.comm_avant = QRadioButton("Démarrer avant la fin du délai")
        # Par défaut : démarrage AVANT la fin du délai de rétractation
        # (cas le plus courant en agence — demande client).
        self.comm_avant.setChecked(True)
        grp2 = QButtonGroup(self)
        grp2.addButton(self.comm_attendre)
        grp2.addButton(self.comm_avant)
        self.date_premiere = QLineEdit()
        self.date_premiere.setPlaceholderText("jj/mm/aaaa")
        self.date_premiere.setFixedWidth(110)
        ligne_c = QHBoxLayout()
        ligne_c.setSpacing(16)
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

    # --------------------------------------------------------------- paiement
    def _build_paiement(self) -> None:
        box, g = _section("Mode de paiement")
        self.paie_prelevement = QRadioButton("Prélèvement automatique (autorisation générée, RIB à joindre)")
        self.paie_virement = QRadioButton("Virement bancaire")
        self.paie_cheque = QRadioButton("Chèque bancaire")
        grp = QButtonGroup(self)
        for b in (self.paie_prelevement, self.paie_virement, self.paie_cheque):
            grp.addButton(b)
            b.toggled.connect(self._toggle_paiement)
        ligne = QHBoxLayout()
        ligne.setSpacing(20)
        ligne.addWidget(self.paie_prelevement)
        ligne.addWidget(self.paie_virement)
        ligne.addWidget(self.paie_cheque)
        ligne.addStretch()
        g.addLayout(ligne, 0, 0)
        self._form.addWidget(box)

    def _mode_paiement(self) -> str:
        if self.paie_prelevement.isChecked():
            return "prelevement"
        if self.paie_virement.isChecked():
            return "virement"
        if self.paie_cheque.isChecked():
            return "cheque"
        return ""

    def _toggle_paiement(self) -> None:
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

        # Réduction commerciale optionnelle (ligne dédiée sur le devis).
        self.remise_active = QCheckBox("Appliquer une réduction")
        self.remise_active.stateChanged.connect(self._toggle_remise)
        self.remise_valeur = QDoubleSpinBox()
        self.remise_valeur.setRange(0.0, 9999.0)
        self.remise_valeur.setDecimals(2)
        self.remise_valeur.setFixedWidth(90)
        self.remise_valeur.valueChanged.connect(self._maj_apercu)
        self.remise_unite = QComboBox()
        self.remise_unite.addItems(["%", "€ TTC / semaine"])
        self.remise_unite.currentIndexChanged.connect(self._maj_apercu)
        ligne_r = QHBoxLayout()
        ligne_r.setSpacing(10)
        ligne_r.addWidget(self.remise_valeur)
        ligne_r.addWidget(self.remise_unite)
        ligne_r.addStretch()
        g.addWidget(self.remise_active, 2, 0, 1, 2)
        g.addLayout(ligne_r, 2, 2, 1, 4)
        self._toggle_remise()
        self._form.addWidget(box)

    def _toggle_remise(self) -> None:
        actif = self.remise_active.isChecked()
        self.remise_valeur.setVisible(actif)  # masqué tant que la case n'est pas cochée
        self.remise_unite.setVisible(actif)
        if not actif:
            self.remise_valeur.setValue(0.0)
        self._maj_apercu()

    # ------------------------------------------------------------- barre bas
    def _build_barre(self, racine: QVBoxLayout) -> None:
        barre = QFrame()
        barre.setObjectName("barreResume")
        barre.setFrameShape(QFrame.StyledPanel)
        lay = QVBoxLayout(barre)
        lay.setContentsMargins(24, 12, 24, 12)

        self.apercu = QLabel("Aperçu : —")
        self.apercu.setObjectName("apercu")
        self.statut = QLabel("")
        self.statut.setObjectName("statut")
        self.sepa_note = QLabel("")

        ligne = QHBoxLayout()
        infos = QVBoxLayout()
        infos.addWidget(self.apercu)
        infos.addWidget(self.statut)
        infos.addWidget(self.sepa_note)
        ligne.addLayout(infos, 1)

        self.bouton = QPushButton("Générer les documents")
        self.bouton.setObjectName("boutonPrincipal")
        self.bouton.setMinimumHeight(44)
        self.bouton.clicked.connect(self._generer)
        ligne.addWidget(self.bouton)

        lay.addLayout(ligne)
        racine.addWidget(barre)

    # --------------------------------------------------------------- collecte
    def _collecter(self) -> SaisieDossier:
        return SaisieDossier(
            civilite=self.civilite.currentText(), prenom=self.prenom.text(), nom=self.nom.text(),
            adresse=self.adresse.text(), cp=self.cp.text(), ville=self.ville.text(),
            tel=self.tel.text(), email=self.email.text(),
            tutelle=self.tutelle.isChecked(),
            tutelle_organisme=self.tutelle_organisme.text(),
            tuteur_prenom=self.tuteur_prenom.text(), tuteur_nom=self.tuteur_nom.text(),
            benef_identique=self.benef_identique.isChecked(),
            benef_prenom=self.benef_prenom.text(), benef_nom=self.benef_nom.text(),
            benef_adresse=self.benef_adresse.text(),
            lieu_prestation=self.lieu_prestation.text(),
            lignes=self.prestations.lignes(),
            remise_active=self.remise_active.isChecked(),
            remise_mode="pourcent" if self.remise_unite.currentIndex() == 0 else "euros",
            remise_valeur=str(self.remise_valeur.value()),
            tournee="T1" if self.tournee_t1.isChecked() else "T2",
            jours_repas=[j for j, cb in self.jours.items() if cb.isChecked()],
            commencement="attendre" if self.comm_attendre.isChecked() else "avant",
            date_premiere_livraison=self.date_premiere.text(),
            mode_paiement=self._mode_paiement(),
            devis_num=self.devis_num.text(), date_devis=self.date_devis.text(),
            date_validite=self.date_validite.text(), lieu=self.lieu.text(),
        )

    # ----------------------------------------------------------------- aperçu
    def _maj_apercu(self) -> None:
        if not hasattr(self, "apercu"):
            return  # barre du bas pas encore construite (appel pendant __init__)
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
        if not hasattr(self, "bouton"):
            return  # barre du bas pas encore construite (appel pendant __init__)
        manques = []
        if not self.nom.text().strip():
            manques.append("nom du client")
        if not self.prestations.lignes():
            manques.append("au moins une formule")
        if not self._mode_paiement():
            manques.append("mode de paiement")
        self.bouton.setEnabled(not manques)
        self.statut.setText("Prêt à générer." if not manques else "Manque : " + ", ".join(manques))

        if self._mode_paiement() == "prelevement":
            self.sepa_note.setText(
                "Autorisation de prélèvement : sera générée (coordonnées bancaires "
                "non saisies — le client joint son RIB)."
            )
            self.sepa_note.setStyleSheet("color: #74A714; font-size: 9pt;")
        else:
            self.sepa_note.setText("Autorisation de prélèvement : non requise.")
            self.sepa_note.setStyleSheet("color: #8A8C7E; font-size: 9pt;")

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
