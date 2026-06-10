"""Habillage visuel — charte Les Menus Services.

100 % visuel (QSS + bandeau logo) : aucune logique, aucun câblage de champ.
Palette EXACTE extraite du logo de la franchise :
- vert pomme  #8CC919  (couleur de marque)
- bordeaux    #661D13  (texte fort, titres)

Principes de la refonte UX :
- bordures de champs en 2 px DÈS l'état normal (couleur claire) : le passage
  au focus ne change que la couleur, jamais l'épaisseur → aucun sautillement ;
- neutres chauds (gris-vert) assortis au fond teinté, pas de gris bleuté ;
- hiérarchie typographique nette (titres bordeaux semibold, libellés gris doux) ;
- scrollbars fines et discrètes, états hover/pressed partout.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.chemins import RACINE

# --- Palette (depuis le logo) --------------------------------------------- #
VERT = "#8CC919"          # vert pomme / anis (marque)
VERT_FONCE = "#74A714"    # survol des boutons verts
VERT_PALE = "#F6FAEC"     # fonds très clairs
BORDEAUX = "#661D13"      # texte fort, titres
BORDEAUX_FONCE = "#4E150E"  # survol bordeaux
TEXTE = "#2E2E2E"
LABEL = "#5F6157"         # libellés de champs (gris-vert doux)
FOND_PAGE = "#F0F3E6"     # fond de page teinté (cartes blanches dessus)
BLANC = "#FFFFFF"

# Neutres chauds (assortis au fond teinté — pas de gris bleuté)
BORDURE_CARTE = "#E8EADD"   # contour des cartes
BORDURE_CHAMP = "#E1E4D3"   # contour des champs au repos (2 px)
BORDURE_HOVER = "#B9C394"   # contour des champs au survol
FOND_CHAMP = "#FDFDFA"      # fond des champs au repos
GRIS_DESACTIVE = "#ABABA3"
FOND_DESACTIVE = "#F2F2EC"

LOGO = RACINE / "assets" / "logo.png"
CHEVRON = RACINE / "assets" / "chevron_bas.png"
PLUS = RACINE / "assets" / "plus.png"
MINUS = RACINE / "assets" / "minus.png"
CHECK = RACINE / "assets" / "check.png"


def feuille_qss() -> str:
    """Feuille de style globale — look « carte » (cartes blanches sur fond teinté)."""
    return f"""
    QWidget {{
        color: {TEXTE};
        font-family: "Segoe UI", "Segoe UI Variable", sans-serif;
        font-size: 10pt;
    }}

    /* Fond de page teinté + zone défilante */
    QScrollArea {{ border: none; background: {FOND_PAGE}; }}
    QWidget#page {{ background: {FOND_PAGE}; }}

    /* Scrollbars fines, discrètes, arrondies */
    QScrollBar:vertical {{
        background: transparent; width: 12px; margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: #C8CDAF; border-radius: 4px; min-height: 40px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {VERT_FONCE}; }}
    QScrollBar:horizontal {{
        background: transparent; height: 12px; margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: #C8CDAF; border-radius: 4px; min-width: 40px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {VERT_FONCE}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    /* Bandeau d'en-tête (hero) */
    QFrame#bandeau {{ background-color: {BLANC}; border-bottom: 3px solid {VERT}; }}
    QLabel#titreApp {{ color: {BORDEAUX}; font-size: 16pt; font-weight: 600; }}
    QLabel#sousTitreApp {{
        color: {VERT_FONCE};
        background-color: {VERT_PALE};
        border: 1px solid #E2EFC4;
        border-radius: 9px;
        padding: 2px 10px;
        font-size: 8.5pt;
        font-weight: 600;
    }}

    /* Sections = cartes blanches arrondies */
    QGroupBox {{
        background-color: {BLANC};
        border: 1px solid {BORDURE_CARTE};
        border-radius: 14px;
        margin-top: 17px;
        padding: 20px 20px 18px 20px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 16px; top: 1px;
        padding: 0 8px;
        color: {BORDEAUX};
        font-size: 11.5pt;
        font-weight: 600;
        background: transparent;
    }}

    QLabel {{ background: transparent; color: {LABEL}; }}

    /* Champs de saisie — bordure 2 px dès le repos : focus = couleur seule,
       épaisseur constante → pas de décalage de mise en page. */
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background-color: {FOND_CHAMP};
        border: 2px solid {BORDURE_CHAMP};
        border-radius: 9px;
        padding: 6px 10px;
        min-height: 19px;
        selection-background-color: {VERT};
        selection-color: {BLANC};
    }}
    QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
        border-color: {BORDURE_HOVER};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: {VERT};
        background-color: {BLANC};
    }}
    QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
        background-color: {FOND_DESACTIVE};
        color: {GRIS_DESACTIVE};
        border-color: {BORDURE_CARTE};
    }}
    QLineEdit::placeholder {{ color: #B4B6A8; }}

    /* Boutons +/- des compteurs : zone cliquable nette, séparée du champ */
    QSpinBox, QDoubleSpinBox {{ padding-right: 26px; }}
    QSpinBox::up-button, QDoubleSpinBox::up-button {{
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 25px;
        border-left: 2px solid {BORDURE_CHAMP};
        border-bottom: 1px solid {BORDURE_CHAMP};
        border-top-right-radius: 7px;
        background-color: {VERT_PALE};
    }}
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        width: 25px;
        border-left: 2px solid {BORDURE_CHAMP};
        border-bottom-right-radius: 7px;
        background-color: {VERT_PALE};
    }}
    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background-color: {VERT}; }}
    QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
    QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {{ background-color: {VERT_FONCE}; }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
        image: url("{PLUS.as_posix()}"); width: 11px; height: 11px;
    }}
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
        image: url("{MINUS.as_posix()}"); width: 11px; height: 11px;
    }}

    QComboBox::drop-down {{
        subcontrol-origin: border;
        subcontrol-position: center right;
        width: 27px;
        border-left: 2px solid {BORDURE_CHAMP};
        background-color: {VERT_PALE};
        border-top-right-radius: 7px;
        border-bottom-right-radius: 7px;
    }}
    QComboBox::drop-down:hover {{ background-color: #ECF5D6; }}
    QComboBox::down-arrow {{ image: url("{CHEVRON.as_posix()}"); width: 14px; height: 14px; }}

    /* Liste déroulante ouverte */
    QComboBox QAbstractItemView {{
        background-color: {BLANC};
        border: 1px solid {BORDURE_HOVER};
        border-radius: 6px;
        padding: 4px;
        outline: none;
        selection-background-color: {VERT_PALE};
        selection-color: {BORDEAUX};
    }}
    QComboBox QAbstractItemView::item {{ padding: 6px 10px; border-radius: 5px; }}

    /* Cases & radios */
    QCheckBox, QRadioButton {{ background: transparent; spacing: 8px; }}
    QCheckBox:hover, QRadioButton:hover {{ color: {BORDEAUX}; }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 18px; height: 18px;
        background-color: {BLANC};
        border: 2px solid {BORDURE_HOVER};
    }}
    QCheckBox::indicator {{ border-radius: 5px; }}
    QRadioButton::indicator {{ border-radius: 11px; }}
    QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {VERT_FONCE}; }}
    QCheckBox::indicator:checked {{
        background-color: {VERT};
        border-color: {VERT};
        image: url("{CHECK.as_posix()}");
    }}
    QRadioButton::indicator:checked {{
        /* cercle vert à point blanc : 10 px de contenu + 6 px de bord = 22 px,
           même encombrement qu'au repos (18 + 2×2) → aucun décalage */
        width: 10px; height: 10px;
        background-color: {BLANC};
        border: 6px solid {VERT};
    }}
    QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
        background-color: {FOND_DESACTIVE}; border-color: {BORDURE_CARTE};
    }}

    /* Boutons « pill » (secondaires : contour bordeaux) */
    QPushButton {{
        background-color: {BLANC};
        color: {BORDEAUX};
        border: 1.5px solid {BORDEAUX};
        border-radius: 18px;
        padding: 8px 18px;
        font-weight: 600;
    }}
    QPushButton:hover {{ background-color: {VERT_PALE}; border-color: {BORDEAUX_FONCE}; }}
    QPushButton:pressed {{ background-color: #ECF5D6; }}
    QPushButton:disabled {{ color: {GRIS_DESACTIVE}; border-color: {BORDURE_CHAMP}; background-color: {FOND_DESACTIVE}; }}

    /* Bouton principal : vert + texte bordeaux (couple du logo) */
    QPushButton#boutonPrincipal {{
        background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #97D424, stop:1 {VERT});
        color: {BORDEAUX};
        border: none;
        border-radius: 24px;
        padding: 13px 34px;
        font-weight: bold;
        font-size: 11pt;
    }}
    QPushButton#boutonPrincipal:hover {{
        background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {VERT}, stop:1 {VERT_FONCE});
        color: {BLANC};
    }}
    QPushButton#boutonPrincipal:pressed {{ background-color: {VERT_FONCE}; color: {BLANC}; }}
    QPushButton#boutonPrincipal:disabled {{ background-color: #E6E6DF; color: {GRIS_DESACTIVE}; }}

    /* Petit bouton de suppression de ligne (✕) : rond, discret, rouge au survol */
    QPushButton#boutonSuppr {{
        background-color: {BLANC};
        color: #9A9A92;
        border: 1.5px solid {BORDURE_CHAMP};
        border-radius: 14px;
        padding: 0;
        font-size: 11pt;
        font-weight: bold;
    }}
    QPushButton#boutonSuppr:hover {{
        background-color: #C0392B; color: {BLANC}; border-color: #C0392B;
    }}

    /* Bouton d'action du bandeau d'en-tête (ex. « Éditer les tarifs ») */
    QPushButton#boutonHeader {{
        background-color: {BLANC};
        color: {BORDEAUX};
        border: 1.5px solid {VERT};
        border-radius: 18px;
        padding: 8px 18px;
        font-weight: 600;
    }}
    QPushButton#boutonHeader:hover {{ background-color: {VERT}; color: {BLANC}; border-color: {VERT}; }}
    QPushButton#boutonHeader:pressed {{ background-color: {VERT_FONCE}; color: {BLANC}; }}

    /* Bouton « Ajouter une formule » : ghost vert, pleine largeur */
    QPushButton#boutonAjouter {{
        background-color: {VERT_PALE};
        color: {BORDEAUX};
        border: 1.5px dashed {VERT};
        border-radius: 12px;
        padding: 9px 14px;
        font-weight: 600;
    }}
    QPushButton#boutonAjouter:hover {{ background-color: #ECF5D6; border-color: {VERT_FONCE}; }}
    QPushButton#boutonAjouter:pressed {{ background-color: #E2F0C8; }}

    /* Barre résumé (pied de fenêtre) */
    QFrame#barreResume {{ background-color: {BLANC}; border-top: 2px solid {VERT}; }}
    QLabel#apercu {{ color: {BORDEAUX}; font-weight: bold; font-size: 11.5pt; }}
    QLabel#statut {{ color: #8A8C7E; font-size: 9pt; }}

    /* Tableaux (éditeur de tarifs) */
    QTableWidget {{
        background-color: {BLANC};
        alternate-background-color: #FAFBF3;
        border: 1px solid {BORDURE_CARTE};
        border-radius: 10px;
        gridline-color: #EFF0E6;
        selection-background-color: {VERT_PALE};
        selection-color: {TEXTE};
    }}
    QTableWidget::item {{ padding: 4px 8px; }}
    QHeaderView::section {{
        background-color: {VERT_PALE};
        color: {BORDEAUX};
        font-weight: 600;
        border: none;
        border-bottom: 2px solid {VERT};
        border-right: 1px solid #EFF0E6;
        padding: 7px 10px;
    }}
    QTableCornerButton::section {{ background-color: {VERT_PALE}; border: none; }}

    /* Listes (éditeur de régimes) */
    QListWidget {{
        background-color: {BLANC};
        border: 1px solid {BORDURE_CARTE};
        border-radius: 10px;
        padding: 6px;
    }}
    QListWidget::item {{ padding: 8px 10px; border-radius: 7px; }}
    QListWidget::item:hover {{ background-color: {VERT_PALE}; }}
    QListWidget::item:selected {{ background-color: {VERT_PALE}; color: {BORDEAUX}; }}

    /* Zone de texte (récapitulatif) */
    QPlainTextEdit, QTextEdit {{
        background-color: {FOND_CHAMP};
        border: 2px solid {BORDURE_CHAMP};
        border-radius: 10px;
        padding: 8px;
        selection-background-color: {VERT};
        selection-color: {BLANC};
    }}

    /* Dialogues */
    QDialog {{ background-color: {FOND_PAGE}; }}
    QMessageBox {{ background-color: {BLANC}; }}
    QMessageBox QPushButton {{ min-width: 90px; }}

    QToolTip {{
        background-color: {BORDEAUX};
        color: {BLANC};
        border: none;
        border-radius: 5px;
        padding: 6px 10px;
        font-size: 9pt;
    }}
    """


def appliquer_ombre(widget: QWidget) -> None:
    """Ombre portée douce (effet 'carte web') sur un widget."""
    effet = QGraphicsDropShadowEffect(widget)
    effet.setBlurRadius(26)
    effet.setXOffset(0)
    effet.setYOffset(4)
    effet.setColor(QColor(70, 75, 40, 30))
    widget.setGraphicsEffect(effet)


def construire_bandeau(boutons: list | None = None) -> QFrame:
    """Bandeau d'en-tête : logo + titre + badge agence, filet vert dessous.

    `boutons` : liste optionnelle de QPushButton (actions globales, ex.
    « Éditer les tarifs ») placés à droite du bandeau.
    """
    bandeau = QFrame()
    bandeau.setObjectName("bandeau")
    lay = QHBoxLayout(bandeau)
    lay.setContentsMargins(20, 12, 20, 12)
    lay.setSpacing(16)

    if LOGO.exists():
        logo = QLabel()
        pix = QPixmap(str(LOGO)).scaledToHeight(54, Qt.SmoothTransformation)
        logo.setPixmap(pix)
        lay.addWidget(logo)

    titres = QVBoxLayout()
    titres.setSpacing(3)
    titre = QLabel("Générateur de documents")
    titre.setObjectName("titreApp")
    sous = QLabel("Les Menus Services — Orange")
    sous.setObjectName("sousTitreApp")
    ligne_sous = QHBoxLayout()  # le badge ne doit pas s'étirer sur toute la largeur
    ligne_sous.setContentsMargins(0, 0, 0, 0)
    ligne_sous.addWidget(sous)
    ligne_sous.addStretch()
    titres.addWidget(titre)
    titres.addLayout(ligne_sous)
    lay.addLayout(titres)
    lay.addStretch()
    for b in boutons or []:
        lay.addWidget(b)
    return bandeau
