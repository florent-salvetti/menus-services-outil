"""Orchestration : saisie unique -> génération de tous les documents d'un dossier.

Couche de GLU entre l'UI et les modules métier. Ne contient AUCUN calcul :
elle mappe les champs saisis vers InfosDevis/InfosMandat/InfosConditions et
appelle calcul / devis / sepa / conditions tels quels. Testable sans Qt.

⚠️ RGPD : l'IBAN/BIC ne sont JAMAIS stockés ici — passés en paramètre aux
générateurs puis abandonnés. Aucune écriture en base.
"""

from __future__ import annotations

import shutil
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from src import compteur
from src.calcul import Resultat, calculer, charger_grille
from src.documents.conditions import InfosConditions, generer_conditions
from src.documents.devis import InfosDevis, generer_devis
from src.documents.sepa import InfosMandat, generer_mandat
from src.iban import IbanInvalide, iban_valide, normaliser

RACINE = Path(__file__).resolve().parent.parent
GRILLE = RACINE / "tarifs.json"
CGV = RACINE / "modeles" / "CGV Les Menus Services Orange client.docx"
DOSSIERS = RACINE / "dossiers"


# --------------------------------------------------------------------------- #
# Saisie (dataclasses plates remplies par l'UI)
# --------------------------------------------------------------------------- #
@dataclass
class LignePrestation:
    formule: str
    nb_repas: int


@dataclass
class SaisieDossier:
    # Client / payeur
    civilite: str = ""
    prenom: str = ""
    nom: str = ""
    adresse: str = ""
    cp: str = ""
    ville: str = ""
    tel: str = ""
    email: str = ""
    # Bénéficiaire
    benef_identique: bool = True
    benef_prenom: str = ""
    benef_nom: str = ""
    benef_adresse: str = ""      # adresse du bénéficiaire (saisie explicite si différent)
    lieu_prestation: str = ""    # lieu de réalisation, distinct de l'adresse
    # Prestations
    lignes: list[LignePrestation] = field(default_factory=list)
    # Livraison
    tournee: str = "T1"
    jours_repas: list[str] = field(default_factory=list)
    commencement: str = "attendre"
    date_premiere_livraison: str = ""
    # Banque (mandat SEPA)
    banque_nom: str = ""
    banque_adresse: str = ""
    iban: str = ""
    bic: str = ""
    # Métadonnées devis
    devis_num: str = ""
    date_devis: str = ""
    date_validite: str = ""
    lieu: str = ""


@dataclass
class ResultatGeneration:
    dossier: Path
    fichiers: list[Path]
    avertissements: list[str]
    resultat: Resultat


# --------------------------------------------------------------------------- #
# Helpers de mise en forme
# --------------------------------------------------------------------------- #
def _sans_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def _slug(s: str) -> str:
    s = _sans_accents(s).strip()
    return "".join(c if c.isalnum() else "-" for c in s).strip("-") or "X"


def nom_dossier(saisie: SaisieDossier, jour: Optional[date] = None) -> str:
    """« NOM_Prénom_AAAA-MM-JJ » (slug sans accents ni espaces)."""
    jour = jour or date.today()
    return f"{_slug(saisie.nom)}_{_slug(saisie.prenom)}_{jour.isoformat()}"


def _client_complet(s: SaisieDossier) -> str:
    return " ".join(x for x in (s.civilite, s.prenom, s.nom) if x.strip()).strip()


def _adresse_complete(s: SaisieDossier) -> str:
    ligne2 = " ".join(x for x in (s.cp, s.ville) if x.strip())
    return ", ".join(x for x in (s.adresse, ligne2) if x.strip())


def _beneficiaire(s: SaisieDossier) -> tuple[str, str, str]:
    """Retourne (prenom, nom, prenom_nom) du bénéficiaire, vides si identique."""
    if s.benef_identique:
        return "", "", ""
    prenom_nom = " ".join(x for x in (s.benef_prenom, s.benef_nom) if x.strip())
    return s.benef_prenom, s.benef_nom, prenom_nom


# --------------------------------------------------------------------------- #
# Calcul (réutilise le moteur, une seule fois)
# --------------------------------------------------------------------------- #
def calculer_saisie(saisie: SaisieDossier) -> Optional[Resultat]:
    """Calcule les totaux pour les lignes valides. None si aucune ligne."""
    lignes = [(l.formule, l.nb_repas) for l in saisie.lignes if l.formule and l.nb_repas > 0]
    if not lignes:
        return None
    grille = charger_grille(GRILLE)
    return calculer(lignes, grille)


# --------------------------------------------------------------------------- #
# Génération complète du dossier
# --------------------------------------------------------------------------- #
def generer_dossier(saisie: SaisieDossier, racine_sortie: Path = DOSSIERS) -> ResultatGeneration:
    """Génère devis + conditions (T1/T2) + mandat SEPA (si IBAN) + CGV.

    - devis et conditions sont TOUJOURS produits.
    - mandat SEPA : seulement si un IBAN valide est fourni (sinon avertissement).
    - IBAN/BIC non persistés.
    """
    resultat = calculer_saisie(saisie)
    if resultat is None:
        raise ValueError("Aucune prestation saisie : impossible de générer.")

    avertissements: list[str] = list(resultat.avertissements)
    fichiers: list[Path] = []

    dossier = racine_sortie / nom_dossier(saisie)
    dossier.mkdir(parents=True, exist_ok=True)

    client_nom = _client_complet(saisie)
    client_adresse = _adresse_complete(saisie)
    benef_prenom, benef_nom, benef_prenom_nom = _beneficiaire(saisie)
    base = f"{_slug(saisie.nom)}_{_slug(saisie.prenom)}"

    # --- Devis --------------------------------------------------------------
    infos_devis = InfosDevis(
        client_nom=client_nom,
        client_adresse=client_adresse,
        devis_num=saisie.devis_num,
        date_devis=saisie.date_devis,
        date_validite=saisie.date_validite,
        beneficiaire=benef_prenom_nom,
        lieu_prestation=saisie.lieu_prestation if not saisie.benef_identique else "",
    )
    fichiers.append(generer_devis(resultat, infos_devis, dossier / f"Devis_{base}.docx"))

    # --- Conditions particulières (selon la tournée) ------------------------
    infos_cond = InfosConditions(
        client_nom=f"{saisie.nom} {saisie.prenom}".strip(),
        client_adresse=client_adresse,
        benef_nom=benef_nom,
        benef_prenom=benef_prenom,
        # Adresse du bénéficiaire : saisie EXPLICITE si différent, jamais
        # l'adresse client par défaut (champ de contrat — on ne devine pas).
        benef_adresse=saisie.benef_adresse if not saisie.benef_identique else "",
        lieu_prestation=saisie.lieu_prestation if not saisie.benef_identique else "",
        commencement=saisie.commencement,
        date_premiere_livraison=saisie.date_premiere_livraison,
        jours_repas=saisie.jours_repas,
        lieu=saisie.lieu,
        date=saisie.date_devis,
    )
    fichiers.append(
        generer_conditions(
            saisie.tournee, infos_cond, resultat,
            dossier / f"Conditions_{saisie.tournee}_{base}.docx",
        )
    )

    # --- Mandat SEPA (uniquement si IBAN fourni ET valide) ------------------
    iban = normaliser(saisie.iban)
    if not iban:
        avertissements.append("Mandat SEPA non généré (pas d'IBAN saisi).")
    elif not iban_valide(iban):
        avertissements.append("IBAN invalide (clé mod 97) : mandat SEPA non généré — vérifiez l'IBAN.")
    else:
        infos_sepa = InfosMandat(
            debiteur_nom=client_nom,
            debiteur_adresse=client_adresse,
            banque_nom=saisie.banque_nom,
            banque_adresse=saisie.banque_adresse,
            lieu_signature=saisie.lieu,
            date_signature=saisie.date_devis,
        )
        try:
            fichiers.append(
                generer_mandat(infos_sepa, iban, saisie.bic, dossier / f"Mandat_SEPA_{base}.docx")
            )
        except IbanInvalide as e:
            avertissements.append(f"Mandat SEPA non généré : {e}")

    # --- CGV (jointes telles quelles) ---------------------------------------
    if CGV.exists():
        cible = dossier / CGV.name
        shutil.copyfile(CGV, cible)
        fichiers.append(cible)
    else:
        avertissements.append("CGV introuvables : non jointes.")

    # Numéro de devis consommé (auto-incrément local).
    if saisie.devis_num:
        compteur.enregistrer_numero(saisie.devis_num)

    return ResultatGeneration(
        dossier=dossier, fichiers=fichiers, avertissements=avertissements, resultat=resultat
    )
