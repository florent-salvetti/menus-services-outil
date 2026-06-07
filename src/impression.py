"""Impression groupée : fusion des documents en un PDF unique.

CLAUDE.md §11 : ordre devis -> conditions -> mandat SEPA -> CGV, PDF fusionné
conservé dans le dossier bénéficiaire puis envoyé à l'imprimante par défaut.

Conversion .docx -> PDF, dans l'ordre de préférence :
  1. Microsoft Word via COM (ExportAsFixedFormat) — meilleure fidélité, 0 Mo
     embarqué quand Word est présent ;
  2. LibreOffice (soffice --headless) — embarqué <app>/libreoffice/ ou chemin
     config.json -> libreoffice.soffice (portable, sans Office) ;
  3. sinon : erreur claire, NON bloquante (les .docx restent dans le dossier).

⚠️ La fusion PDF est un CONFORT : un échec de conversion ne doit JAMAIS faire
perdre les .docx déjà générés (générés en amont par dossier.generer_dossier).
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

#: Constante Word : wdExportFormatPDF
_WD_PDF = 17


class SofficeIntrouvable(FileNotFoundError):
    """LibreOffice (soffice) n'a été trouvé ni embarqué ni dans config.json."""


class ConversionImpossible(RuntimeError):
    """Aucun convertisseur (Word puis LibreOffice) n'a pu produire le PDF."""


# --------------------------------------------------------------------------- #
# Convertisseur 1 : Microsoft Word via COM
# --------------------------------------------------------------------------- #
def _convertir_word(docx_list: list[Path], outdir: Path) -> list[Path]:
    """Convertit chaque .docx en PDF via une instance Word DÉDIÉE et ISOLÉE.

    - DispatchEx => NOUVELLE instance (ne touche jamais à un Word déjà ouvert
      par l'utilisateur) ;
    - Visible=False, DisplayAlerts=0 ;
    - documents ouverts en lecture seule (les .docx sources ne sont jamais
      modifiés) ;
    - Quit + libération COM GARANTIS dans finally (pas de process fantôme).
    """
    import pythoncom
    import win32com.client as win32

    pythoncom.CoInitialize()
    word = None
    pdfs: list[Path] = []
    try:
        word = win32.DispatchEx("Word.Application")  # instance neuve, isolée
        word.Visible = False
        word.DisplayAlerts = 0
        for docx in docx_list:
            doc = word.Documents.Open(str(docx.resolve()), ReadOnly=True)
            try:
                pdf = outdir / f"{docx.stem}.pdf"
                doc.ExportAsFixedFormat(str(pdf.resolve()), ExportFormat=_WD_PDF)
                pdfs.append(pdf)
            finally:
                doc.Close(SaveChanges=0)  # wdDoNotSaveChanges
        return pdfs
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:  # noqa: BLE001 — fermeture best-effort
                pass
        pythoncom.CoUninitialize()


# --------------------------------------------------------------------------- #
# Convertisseur 2 : LibreOffice (repli portable)
# --------------------------------------------------------------------------- #
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


def _soffice_pdf(docx: Path, outdir: Path, soffice: Path, profil: Path) -> Path:
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


def _convertir_libreoffice(docx_list: list[Path], outdir: Path, soffice: Path) -> list[Path]:
    profil = Path(tempfile.mkdtemp(prefix="lms_loprofile_"))
    try:
        return [_soffice_pdf(f, outdir, soffice, profil) for f in docx_list]
    finally:
        shutil.rmtree(profil, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Orchestration conversion (Word -> LibreOffice -> erreur claire)
# --------------------------------------------------------------------------- #
def convertir(
    docx_list: list[Path],
    outdir: Path,
    soffice: Optional[Path] = None,
    moteur: Optional[str] = None,
) -> list[Path]:
    """Convertit les .docx en PDF : Word d'abord, puis LibreOffice.

    `moteur` force un convertisseur ("word" ou "libreoffice") ; None = auto.
    Lève ConversionImpossible si aucun n'aboutit (message exploitable par l'UI).
    """
    erreurs: list[str] = []

    if moteur in (None, "word"):
        try:
            return _convertir_word(docx_list, outdir)
        except Exception as e:  # noqa: BLE001 — on bascule sur le repli
            erreurs.append(f"Word : {e}")

    if moteur in (None, "libreoffice"):
        try:
            soff = Path(soffice) if soffice else trouver_soffice()
            return _convertir_libreoffice(docx_list, outdir, soff)
        except Exception as e:  # noqa: BLE001
            erreurs.append(f"LibreOffice : {e}")

    raise ConversionImpossible(
        "Conversion PDF impossible (ni Word, ni LibreOffice).\n"
        "Les documents .docx restent disponibles dans le dossier.\n"
        + "\n".join(erreurs)
    )


def pdf_dossier_complet(
    fichiers_docx,
    sortie: Path,
    soffice: Optional[Path] = None,
    moteur: Optional[str] = None,
) -> Path:
    """Convertit chaque .docx (dans l'ordre fourni) et fusionne en un PDF unique.

    `fichiers_docx` : chemins .docx dans l'ordre devis -> conditions -> SEPA ->
    CGV (ordre renvoyé par generer_dossier). `sortie` : PDF fusionné final.
    """
    docx = [Path(f) for f in fichiers_docx if Path(f).suffix.lower() == ".docx"]
    if not docx:
        raise ValueError("Aucun document .docx à fusionner.")

    tmp_pdf = Path(tempfile.mkdtemp(prefix="lms_pdf_"))
    try:
        writer = PdfWriter()
        for pdf in convertir(docx, tmp_pdf, soffice, moteur):
            writer.append(str(pdf))
        sortie = Path(sortie)
        with open(sortie, "wb") as fh:
            writer.write(fh)
        writer.close()
        return sortie
    finally:
        shutil.rmtree(tmp_pdf, ignore_errors=True)


def imprimer(pdf: Path) -> None:
    """Envoie le PDF à l'imprimante par défaut (Windows). Ouvre à défaut."""
    pdf = Path(pdf)
    try:
        os.startfile(str(pdf), "print")  # type: ignore[attr-defined]
    except OSError:
        os.startfile(str(pdf))  # type: ignore[attr-defined]
