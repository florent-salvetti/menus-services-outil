"""Habillage visuel — charte Les Menus Services.

100 % visuel (QSS + bandeau logo) : aucune logique, aucun câblage de champ.
Palette EXACTE extraite du logo de la franchise :
- vert pomme  #8CC919  (couleur de marque)
- bordeaux    #661D13  (texte fort, titres)
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
LABEL = "#5A5A5A"         # libellés de champs (gris doux, façon web)
BORDURE = "#DDDDDD"
FOND_PAGE = "#EEF2E2"     # fond de page teinté (cartes blanches dessus)
BLANC = "#FFFFFF"

LOGO = RACINE / "assets" / "logo.png"
CHEVRON = RACINE / "assets" / "chevron_bas.png"


def feuille_qss() -> str:
    """Feuille de style globale — look « carte » (cartes blanches sur fond teinté)."""
    return f"""
    QWidget {{ color: {TEXTE}; font-size: 10pt; }}

    /* Fond de page teinté + zone défilante */
    QScrollArea {{ border: none; background: {FOND_PAGE}; }}
    QWidget#page {{ background: {FOND_PAGE}; }}

    /* Bandeau d'en-tête (hero) */
    QFrame#bandeau {{ background-color: {BLANC}; border-bottom: 3px solid {VERT}; }}
    QLabel#titreApp {{ color: {BORDEAUX}; font-size: 17pt; font-weight: bold; }}

    /* Sections = cartes blanches arrondies */
    QGroupBox {{
        background-color: {BLANC};
        border: 1px solid #ECECEC;
        border-radius: 14px;
        margin-top: 16px;
        padding: 18px 18px 16px 18px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 18px; top: 0px;
        padding: 0 6px;
        color: {BORDEAUX};
        font-size: 12pt;
        font-weight: bold;
        background: transparent;
    }}

    QLabel {{ background: transparent; color: {LABEL}; }}

    /* Champs de saisie */
    QLineEdit, QComboBox, QSpinBox {{
        background-color: {BLANC};
        border: 1px solid {BORDURE};
        border-radius: 9px;
        padding: 7px 10px;
        min-height: 18px;
        selection-background-color: {VERT};
        selection-color: {BLANC};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 2px solid {VERT}; }}
    QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{ border: 1px solid {VERT_FONCE}; }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        width: 26px;
        border-left: 1px solid {BORDURE};
        background-color: {VERT_PALE};
        border-top-right-radius: 9px;
        border-bottom-right-radius: 9px;
    }}
    QComboBox::down-arrow {{ image: url("{CHEVRON.as_posix()}"); width: 14px; height: 14px; }}

    /* Cases & radios */
    QCheckBox, QRadioButton {{ background: transparent; spacing: 8px; }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 17px; height: 17px;
        background-color: {BLANC};
        border: 1px solid {BORDURE};
    }}
    QCheckBox::indicator {{ border-radius: 5px; }}
    QRadioButton::indicator {{ border-radius: 9px; }}
    QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border: 1px solid {VERT_FONCE}; }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background-color: {VERT}; border: 1px solid {VERT_FONCE};
    }}

    /* Boutons « pill » (secondaires : contour bordeaux) */
    QPushButton {{
        background-color: {BLANC};
        color: {BORDEAUX};
        border: 1.5px solid {BORDEAUX};
        border-radius: 18px;
        padding: 7px 16px;
        font-weight: 600;
    }}
    QPushButton:hover {{ background-color: {VERT_PALE}; }}
    QPushButton:disabled {{ color: #A8A8A8; border-color: {BORDURE}; }}

    /* Bouton principal : vert + texte bordeaux (couple du logo) */
    QPushButton#boutonPrincipal {{
        background-color: {VERT};
        color: {BORDEAUX};
        border: none;
        border-radius: 23px;
        padding: 12px 30px;
        font-weight: bold;
        font-size: 11pt;
    }}
    QPushButton#boutonPrincipal:hover {{ background-color: {VERT_FONCE}; color: {BLANC}; }}
    QPushButton#boutonPrincipal:disabled {{ background-color: #E4E4E4; color: #A8A8A8; }}

    /* Petit bouton de suppression de ligne (✕) : rond, discret, rouge au survol */
    QPushButton#boutonSuppr {{
        background-color: {BLANC};
        color: #9A9A9A;
        border: 1px solid {BORDURE};
        border-radius: 14px;
        padding: 0;
        font-size: 11pt;
        font-weight: bold;
    }}
    QPushButton#boutonSuppr:hover {{
        background-color: #C0392B; color: {BLANC}; border-color: #C0392B;
    }}

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

    /* Barre résumé */
    QFrame#barreResume {{ background-color: {BLANC}; border-top: 2px solid {VERT}; }}
    QLabel#apercu {{ color: {BORDEAUX}; font-weight: bold; font-size: 11pt; }}

    QToolTip {{ background-color: {BORDEAUX}; color: {BLANC}; border: none; padding: 5px; }}
    """


def appliquer_ombre(widget: QWidget) -> None:
    """Ombre portée douce (effet 'carte web') sur un widget."""
    effet = QGraphicsDropShadowEffect(widget)
    effet.setBlurRadius(20)
    effet.setXOffset(0)
    effet.setYOffset(3)
    effet.setColor(QColor(60, 50, 30, 45))
    widget.setGraphicsEffect(effet)


def construire_bandeau() -> QFrame:
    """Bandeau d'en-tête : logo + titre, filet vert dessous. Décoratif."""
    bandeau = QFrame()
    bandeau.setObjectName("bandeau")
    lay = QHBoxLayout(bandeau)
    lay.setContentsMargins(14, 10, 14, 10)
    lay.setSpacing(14)

    if LOGO.exists():
        logo = QLabel()
        pix = QPixmap(str(LOGO)).scaledToHeight(56, Qt.SmoothTransformation)
        logo.setPixmap(pix)
        lay.addWidget(logo)

    titres = QVBoxLayout()
    titres.setSpacing(0)
    titre = QLabel("Générateur de documents")
    titre.setObjectName("titreApp")
    sous = QLabel("Les Menus Services — Orange")
    sous.setStyleSheet(f"color: {VERT_FONCE}; font-size: 9pt;")
    titres.addWidget(titre)
    titres.addWidget(sous)
    lay.addLayout(titres)
    lay.addStretch()
    return bandeau
