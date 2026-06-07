"""OCR du RIB (local) — lecture d'IBAN/BIC depuis un RIB scanné (image ou PDF).

CLAUDE.md §9 :
- 100 % local (Tesseract embarqué, chemin relatif — JAMAIS d'install système).
- L'IBAN lu est TOUJOURS soumis à validation humaine dans l'UI (champ éditable).
- IBAN/BIC non persistés ; l'image source de l'utilisateur n'est NI copiée NI
  supprimée. La rasterisation PDF se fait EN MÉMOIRE (aucun fichier temporaire).

Conception : la logique d'extraction (`extraire_iban`, `extraire_bic`) est PURE
et testable sans Tesseract. Seul `lire_rib` dépend de Tesseract/PyMuPDF, importés
paresseusement.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.iban import bic_valide, iban_valide, normaliser

# --- Tesseract EMBARQUÉ (portable, chemin relatif) ------------------------- #
from src.chemins import RACINE
TESSERACT_DIR = RACINE / "tesseract"
TESSERACT_EXE = TESSERACT_DIR / "tesseract.exe"
TESSDATA = TESSERACT_DIR / "tessdata"
LANGUE = "fra"  # repli sur 'eng' si fra.traineddata absent


# --------------------------------------------------------------------------- #
# Extraction PURE (testable sans Tesseract)
# --------------------------------------------------------------------------- #
def _candidats_iban(texte: str) -> list[str]:
    """Repère les séquences plausibles d'IBAN FR (FR + 2 chiffres + 23 alnum)."""
    t = texte.upper()
    candidats: list[str] = []
    for m in re.finditer(r"FR", t):
        # 1er caractère alphanumérique après « FR » doit être un CHIFFRE (clé).
        j = m.end()
        while j < len(t) and not t[j].isalnum():
            if t[j] not in " \t\n\r.-":
                break
            j += 1
        if j >= len(t) or not t[j].isdigit():
            continue
        # Rassemble FR + 25 alnum, en tolérant espaces/tirets/points/retours.
        s = ["F", "R"]
        k = m.end()
        while k < len(t) and len(s) < 27:
            ch = t[k]
            if ch.isalnum():
                s.append(ch)
            elif ch in " \t\n\r.-":
                pass
            else:
                break
            k += 1
        cand = "".join(s)
        if len(cand) == 27 and cand[2:4].isdigit():
            candidats.append(cand)
    return list(dict.fromkeys(candidats))  # dédoublonne en gardant l'ordre


def extraire_iban(texte: str) -> Optional[str]:
    """Extrait le meilleur IBAN du texte OCR.

    Priorité : (1) candidat directement valide (mod 97) ; sinon (2) le 1er
    candidat plausible, renvoyé TEL QUEL (invalide) pour correction humaine.
    None si rien de plausible.

    PAS d'auto-correction des confusions OCR : une « correction » pourrait
    produire un IBAN valide au mod 97 mais FAUX, et tromper la validation
    humaine. On préfère surfacer le brut et laisser l'utilisateur corriger.
    """
    candidats = _candidats_iban(texte)
    for c in candidats:
        if iban_valide(c):
            return c
    return candidats[0] if candidats else None


def extraire_bic(texte: str) -> Optional[str]:
    """Extrait un BIC du texte OCR.

    Deux garde-fous (leçon d'un vrai RIB) :
    1. on ne retient QUE des candidats valides (`bic_valide` : format + code
       pays ISO) — « IDENTITE » (pays « TI ») est écarté ;
    2. on PRIVILÉGIE le candidat le plus proche APRÈS un libellé « BIC » /
       « SWIFT » / « Bank Identifier Code », car des mots du document peuvent
       fortuitement avoir la forme d'un BIC valide (« BANCAIRE » → pays « AI »).
    Sinon, repli sur le 1er candidat valide.
    """
    t = texte.upper()
    candidats = [
        (m.start(), m.group(0))
        for m in re.finditer(r"\b[A-Z]{6}[0-9A-Z]{2}(?:[0-9A-Z]{3})?\b", t)
        if bic_valide(m.group(0))
    ]
    if not candidats:
        return None

    libelles = [m.end() for m in re.finditer(r"BIC|SWIFT|BANK\s+IDENTIFIER\s+CODE", t)]
    if libelles:
        meilleur = None
        for pos, bic in candidats:
            apres = [pos - lp for lp in libelles if pos >= lp]
            if apres and (meilleur is None or min(apres) < meilleur[0]):
                meilleur = (min(apres), bic)
        if meilleur:
            return meilleur[1]
    return candidats[0][1]


# --------------------------------------------------------------------------- #
# Lecture d'un RIB (image ou PDF) via Tesseract embarqué
# --------------------------------------------------------------------------- #
@dataclass
class ResultatOCR:
    iban: Optional[str]          # meilleur IBAN reconnu (normalisé) ou None
    iban_valide: bool            # clé mod 97 OK ?
    bic: Optional[str]
    texte_brut: str              # texte OCR (debug / affichage)


def _configurer_tesseract():
    """Pointe pytesseract vers le Tesseract EMBARQUÉ (chemin relatif).

    Aucune dépendance à une install système. Lève une erreur claire si le
    binaire embarqué est absent du dossier de l'app.
    """
    import pytesseract  # import paresseux : pas requis pour l'extraction pure

    if not TESSERACT_EXE.exists():
        raise FileNotFoundError(
            f"Tesseract embarqué introuvable : {TESSERACT_EXE}. "
            "Placez tesseract.exe + tessdata/ dans le dossier 'tesseract/' de l'app "
            "(voir la procédure d'installation portable)."
        )
    pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_EXE)
    if TESSDATA.exists():
        os.environ["TESSDATA_PREFIX"] = str(TESSDATA)
    return pytesseract


def _charger_image(chemin: Path):
    """Charge une image ou la 1re page d'un PDF EN MÉMOIRE (aucun temporaire)."""
    from PIL import Image  # import paresseux

    if chemin.suffix.lower() == ".pdf":
        import fitz  # PyMuPDF, import paresseux
        from io import BytesIO

        doc = fitz.open(str(chemin))
        try:
            page = doc.load_page(0)
            # rendu haute résolution (≈300 dpi) pour fiabiliser l'OCR
            pix = page.get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72))
            img = Image.open(BytesIO(pix.tobytes("png")))
            img.load()  # force la lecture avant fermeture du doc
            return img
        finally:
            doc.close()
    return Image.open(chemin)


def _pretraiter(img):
    """Niveaux de gris + autocontraste + upscale ×2 (fiabilise l'OCR)."""
    from PIL import ImageOps

    img = ImageOps.grayscale(img)
    img = ImageOps.autocontrast(img)
    img = img.resize((img.width * 2, img.height * 2))
    return img


def lire_rib(chemin: str | Path) -> ResultatOCR:
    """Lit un RIB (image/PDF) et en extrait IBAN + BIC, EN MÉMOIRE.

    L'image source n'est ni copiée ni supprimée. Le résultat doit être soumis à
    validation humaine avant usage (le champ IBAN de l'UI reste éditable).
    """
    chemin = Path(chemin)
    pytesseract = _configurer_tesseract()
    img = _pretraiter(_charger_image(chemin))

    langue = LANGUE if (TESSDATA / f"{LANGUE}.traineddata").exists() else "eng"
    texte = pytesseract.image_to_string(img, lang=langue)

    iban = extraire_iban(texte)
    return ResultatOCR(
        iban=normaliser(iban) if iban else None,
        iban_valide=bool(iban) and iban_valide(iban),
        bic=extraire_bic(texte),
        texte_brut=texte,
    )
