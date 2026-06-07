"""Impression groupée : fusion des documents en un PDF unique, via LibreOffice.

CLAUDE.md §11 : ordre devis -> conditions -> mandat SEPA -> CGV, PDF fusionné
conservé dans le dossier bénéficiaire puis envoyé à l'imprimante par défaut.

LibreOffice (soffice) — gestion portable (option 3) :
1. binaire EMBARQUÉ : <app>/libreoffice/program/soffice.exe (chemin relatif) ;
2. sinon chemin renseigné dans config.json -> libreoffice.soffice ;
3. sinon erreur claire avec la procédure (comme Tesseract).

Aucune dépendance au PATH système. La conversion utilise un profil LibreOffice
isolé et temporaire (n'entre pas en conflit avec une instance déjà ouverte) ;
les PDF intermédiaires sont temporaires — seul le PDF fusionné est conservé.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from pypdf import PdfWriter

RACINE = Path(__file__).resolve().parent.parent
_SOFFICE_EMBARQUE = RACINE / "libreoffice" / "program" / "soffice.exe"
_CONFIG = RACINE / "config.json"


class SofficeIntrouvable(FileNotFoundError):
    """LibreOffice (soffice) n'a été trouvé ni embarqué ni dans config.json."""


def trouver_soffice() -> Path:
    """Localise soffice : embarqué d'abord, puis config.json. Sinon lève."""
    if _SOFFICE_EMBARQUE.exists():
        return _SOFFICE_EMBARQUE
    try:
        cfg = json.loads(_CONFIG.read_text(encoding="utf-8"))
        chemin = cfg.get("libreoffice", {}).get("soffice", "")
        if chemin and Path(chemin).exists():
            return Path(chemin)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    raise SofficeIntrouvable(
        "LibreOffice (soffice) introuvable.\n"
        f"• Placez LibreOffice Portable dans {_SOFFICE_EMBARQUE.parent.parent} "
        "(…/libreoffice/program/soffice.exe),\n"
        "• OU renseignez le chemin dans config.json → libreoffice.soffice."
    )


def _convertir_en_pdf(docx: Path, outdir: Path, soffice: Path, profil: Path) -> Path:
    """Convertit un .docx en .pdf via soffice headless (profil isolé)."""
    cmd = [
        str(soffice),
        f"-env:UserInstallation=file:///{profil.as_posix()}",
        "--headless", "--norestore",
        "--convert-to", "pdf",
        "--outdir", str(outdir),
        str(docx),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=180)
    pdf = outdir / f"{docx.stem}.pdf"
    if not pdf.exists():
        raise RuntimeError(f"Conversion PDF échouée pour « {docx.name} ».")
    return pdf


def pdf_dossier_complet(
    fichiers_docx, sortie: Path, soffice: Optional[Path] = None
) -> Path:
    """Convertit chaque .docx (dans l'ordre fourni) et fusionne en un PDF unique.

    `fichiers_docx` : chemins .docx dans l'ordre devis -> conditions -> SEPA ->
    CGV (ordre renvoyé par generer_dossier). `sortie` : PDF fusionné final.
    """
    soffice = Path(soffice) if soffice else trouver_soffice()
    docx = [Path(f) for f in fichiers_docx if Path(f).suffix.lower() == ".docx"]
    if not docx:
        raise ValueError("Aucun document .docx à fusionner.")

    tmp_pdf = Path(tempfile.mkdtemp(prefix="lms_pdf_"))
    profil = Path(tempfile.mkdtemp(prefix="lms_loprofile_"))
    try:
        writer = PdfWriter()
        for f in docx:
            writer.append(str(_convertir_en_pdf(f, tmp_pdf, soffice, profil)))
        sortie = Path(sortie)
        with open(sortie, "wb") as fh:
            writer.write(fh)
        writer.close()
        return sortie
    finally:
        shutil.rmtree(tmp_pdf, ignore_errors=True)
        shutil.rmtree(profil, ignore_errors=True)


def imprimer(pdf: Path) -> None:
    """Envoie le PDF à l'imprimante par défaut (Windows). Ouvre à défaut."""
    pdf = Path(pdf)
    try:
        os.startfile(str(pdf), "print")  # type: ignore[attr-defined]
    except OSError:
        os.startfile(str(pdf))  # type: ignore[attr-defined]
