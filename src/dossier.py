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

from decimal import Decimal, InvalidOperation

from src import compteur
from src.calcul import Remise, Resultat, calculer, charger_grille, fmt_eur
from src.documents.cgv import generer_cgv
from src.documents.conditions import InfosConditions, generer_conditions
from src.documents.devis import InfosDevis, _nom_ligne, generer_devis
from src.documents.sepa import InfosMandat, generer_mandat

from src.chemins import RACINE
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
    regime: str = ""  # régime particulier : "diabétique", "sans sel", "mixé" ou ""


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
    # Tutelle (client protégé : les documents mentionnent le représentant)
    tutelle: bool = False
    tutelle_organisme: str = ""
    tuteur_prenom: str = ""
    tuteur_nom: str = ""
    # Bénéficiaire
    benef_identique: bool = True
    benef_prenom: str = ""
    benef_nom: str = ""
    benef_adresse: str = ""      # adresse du bénéficiaire (saisie explicite si différent)
    lieu_prestation: str = ""    # lieu de réalisation, distinct de l'adresse
    # Prestations
    lignes: list[LignePrestation] = field(default_factory=list)
    # Réduction commerciale (devis)
    remise_active: bool = False
    remise_mode: str = "pourcent"   # "pourcent" ou "euros" (TTC / semaine)
    remise_valeur: str = ""         # saisie brute, convertie en Decimal
    # Livraison
    tournee: str = "T1"
    jours_repas: list[str] = field(default_factory=list)
    commencement: str = "attendre"
    date_premiere_livraison: str = ""
    # Paiement — l'autorisation de prélèvement n'est générée QUE pour
    # "prelevement", SANS coordonnées bancaires (le client joint son RIB).
    mode_paiement: str = ""         # "prelevement", "virement", "cheque" ou ""
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
    recap: str = ""


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


def _tuteur_detail(s: SaisieDossier) -> str:
    """« Prénom NOM (Organisme) » du tuteur, vide si pas de tutelle."""
    if not s.tutelle:
        return ""
    tuteur = " ".join(x for x in (s.tuteur_prenom, s.tuteur_nom) if x.strip())
    organisme = s.tutelle_organisme.strip()
    if tuteur and organisme:
        return f"{tuteur} ({organisme})"
    return tuteur or organisme


def _mention_tutelle(s: SaisieDossier) -> str:
    """« Sous tutelle — représenté par Prénom NOM (Organisme) », vide sinon."""
    if not s.tutelle:
        return ""
    detail = _tuteur_detail(s)
    return f"Sous tutelle — représenté par {detail}" if detail else "Sous tutelle"


def _remise(s: SaisieDossier) -> Optional[Remise]:
    """Construit la Remise depuis la saisie (None si inactive ou invalide)."""
    if not s.remise_active:
        return None
    try:
        valeur = Decimal(str(s.remise_valeur).replace(",", ".").strip() or "0")
    except InvalidOperation:
        return None
    if valeur <= 0:
        return None
    return Remise(mode=s.remise_mode, valeur=valeur)


# --------------------------------------------------------------------------- #
# Calcul (réutilise le moteur, une seule fois)
# --------------------------------------------------------------------------- #
def calculer_saisie(saisie: SaisieDossier) -> Optional[Resultat]:
    """Calcule les totaux pour les lignes valides. None si aucune ligne."""
    lignes = [
        (l.formule, l.nb_repas, l.regime)
        for l in saisie.lignes if l.formule and l.nb_repas > 0
    ]
    if not lignes:
        return None
    grille = charger_grille(GRILLE)
    return calculer(lignes, grille, remise=_remise(saisie))


# --------------------------------------------------------------------------- #
# Récapitulatif copiable (à reporter manuellement dans le CRM)
# --------------------------------------------------------------------------- #
def recapitulatif(saisie: SaisieDossier, resultat: Resultat) -> str:
    """Texte propre des infos clés du dossier, pour copier-coller vers le CRM.

    L'outil ne touche jamais au CRM : ce texte est juste fourni à recopier.
    Le reste à charge affiché est `total_apres_ci` (crédit sur la part service).
    """
    lignes: list[str] = []
    titre = f"Devis {saisie.devis_num}" if saisie.devis_num else "Devis"
    lignes.append(f"=== DOSSIER — {titre} — {saisie.date_devis} ===")
    lignes.append("")

    lignes.append(f"CLIENT       {_client_complet(saisie)}")
    adr = _adresse_complete(saisie)
    if adr:
        lignes.append(f"             {adr}")
    contact = " · ".join(
        x for x in (
            f"Tél {saisie.tel}" if saisie.tel.strip() else "",
            f"Email {saisie.email}" if saisie.email.strip() else "",
        ) if x
    )
    if contact:
        lignes.append(f"             {contact}")
    tutelle = _mention_tutelle(saisie)
    if tutelle:
        lignes.append(f"TUTELLE      {tutelle.removeprefix('Sous tutelle — ')}")

    if not saisie.benef_identique:
        _, _, prenom_nom = _beneficiaire(saisie)
        lignes.append(f"BÉNÉFICIAIRE {prenom_nom}")
        if saisie.benef_adresse.strip():
            lignes.append(f"             {saisie.benef_adresse}")
        if saisie.lieu_prestation.strip():
            lignes.append(f"             Lieu de prestation : {saisie.lieu_prestation}")

    tournee = "T1 (Lun/Jeu)" if saisie.tournee == "T1" else "T2 (Mar/Ven)"
    jours = ", ".join(saisie.jours_repas) if saisie.jours_repas else "—"
    lignes.append(f"LIVRAISON    Tournée {tournee} · Jours : {jours}")

    presta = " + ".join(f"{_nom_ligne(l)} ×{l.quantite}" for l in resultat.lignes)
    lignes.append(f"PRESTATIONS  {presta}  ({resultat.nb_repas_total} repas/sem.)")

    if resultat.remise_hebdo_ttc > 0:
        lignes.append(
            f"REMISE       -{fmt_eur(resultat.remise_hebdo_ttc)} TTC / semaine "
            f"(prix public {fmt_eur(resultat.prix_public_hebdo_ttc)})"
        )
    lignes.append(
        f"MONTANTS     Hebdo {fmt_eur(resultat.total_hebdo_ttc)} TTC "
        f"({fmt_eur(resultat.total_hebdo_ht)} HT)"
    )
    lignes.append(f"             Mensuel moyen {fmt_eur(resultat.cout_mensuel_ttc)} TTC")
    lignes.append(
        f"             Reste à charge après crédit d'impôt : "
        f"{fmt_eur(resultat.total_apres_ci)} / mois"
    )

    paiement = {
        "prelevement": "Prélèvement automatique (RIB à joindre par le client)",
        "virement": "Virement bancaire",
        "cheque": "Chèque bancaire",
    }.get(saisie.mode_paiement)
    if paiement:
        lignes.append(f"PAIEMENT     {paiement}")

    if resultat.avertissements:
        lignes.append("")
        lignes.extend(f"⚠ {a}" for a in resultat.avertissements)

    return "\n".join(lignes)


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

    # Tutelle : la mention suit l'identité du client sur chaque document
    # (docxtpl rend « \n » comme un saut de ligne).
    tutelle = _mention_tutelle(saisie)
    client_nom_doc = f"{client_nom}\n{tutelle}" if tutelle else client_nom

    # --- Devis --------------------------------------------------------------
    # En-tête coordonnées (révision client 11/06/2026) : « M./Mme NOM Prénom »
    # sur UNE ligne, puis l'adresse, puis « CP Ville ».
    nom_prenom = " ".join(
        x for x in (saisie.nom.strip().upper(), saisie.prenom.strip()) if x
    )
    infos_devis = InfosDevis(
        civilite=saisie.civilite.strip(),
        client_nom=f"{nom_prenom}\n{tutelle}" if tutelle else nom_prenom,
        client_rue=saisie.adresse.strip(),
        client_cp_ville=" ".join(x for x in (saisie.cp.strip(), saisie.ville.strip()) if x),
        devis_num=saisie.devis_num,
        date_devis=saisie.date_devis,
        date_validite=saisie.date_validite,
        beneficiaire=benef_prenom_nom,
        lieu_prestation=saisie.lieu_prestation if not saisie.benef_identique else "",
    )
    fichiers.append(generer_devis(resultat, infos_devis, dossier / f"Devis_{base}.docx"))

    # --- Conditions particulières (selon la tournée) ------------------------
    # Conditions : la trame a son PROPRE bloc tutelle (« Si le client a été
    # placé sous tutelle… représenté par …, tuteur ») → on le remplit, sans
    # dupliquer la mention sous l'identité.
    # Article 1 (identité du bénéficiaire) : TOUJOURS rempli (retour client) —
    # avec l'identité du client quand le bénéficiaire est identique.
    infos_cond = InfosConditions(
        client_nom=f"{saisie.nom} {saisie.prenom}".strip(),
        client_adresse=client_adresse,
        tuteur=_tuteur_detail(saisie),
        benef_nom=benef_nom if not saisie.benef_identique else saisie.nom,
        benef_prenom=benef_prenom if not saisie.benef_identique else saisie.prenom,
        benef_adresse=saisie.benef_adresse if not saisie.benef_identique else client_adresse,
        lieu_prestation=saisie.lieu_prestation if not saisie.benef_identique else "",
        commencement=saisie.commencement,
        date_premiere_livraison=saisie.date_premiere_livraison,
        jours_repas=saisie.jours_repas,
        mode_paiement=saisie.mode_paiement,
        lieu=saisie.lieu,
        date=saisie.date_devis,
    )
    fichiers.append(
        generer_conditions(
            saisie.tournee, infos_cond, resultat,
            dossier / f"Conditions_Particulieres_{saisie.tournee}_{base}.docx",
        )
    )

    # --- Autorisation de prélèvement (si paiement par prélèvement) ----------
    # Générée SANS coordonnées bancaires (demande client) : le client joint
    # son RIB, comme l'indique la trame. Aucune saisie d'IBAN dans l'outil.
    if saisie.mode_paiement == "prelevement":
        infos_sepa = InfosMandat(
            debiteur_nom=client_nom_doc,
            debiteur_adresse=client_adresse,
            lieu_signature=saisie.lieu,
            date_signature=saisie.date_devis,
        )
        fichiers.append(
            generer_mandat(infos_sepa, None, "", dossier / f"Mandat_SEPA_{base}.docx")
        )

    # --- CGV (jointes, zone de signature remplie : Nom/Prénom/Date) ---------
    if CGV.exists():
        cible = dossier / f"CGV_{base}.docx"
        try:
            generer_cgv(saisie.nom, saisie.prenom, saisie.date_devis, cible, modele=CGV)
        except Exception:  # noqa: BLE001 — CGV toujours jointes, même non remplies
            shutil.copyfile(CGV, cible)
            avertissements.append("CGV jointes sans Nom/Prénom/Date (remplissage impossible).")
        fichiers.append(cible)
    else:
        avertissements.append("CGV introuvables : non jointes.")

    # Numéro de devis consommé (auto-incrément local).
    if saisie.devis_num:
        compteur.enregistrer_numero(saisie.devis_num)

    return ResultatGeneration(
        dossier=dossier,
        fichiers=fichiers,
        avertissements=avertissements,
        resultat=resultat,
        recap=recapitulatif(saisie, resultat),
    )
