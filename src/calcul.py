"""Moteur de calcul tarifaire — Générateur de documents Les Menus Services.

Spécification : CLAUDE.md §6 et §7.

Principes :
- On calcule LIGNE PAR LIGNE puis on consolide (somme).
- Tout est calculé en pleine précision (Decimal) ; l'arrondi à 2 décimales
  n'intervient QU'À L'AFFICHAGE (cf. `fmt_eur`).
- Crédit d'impôt 50 % (correction du §7, confirmée par le client) :
    * le crédit de 50 % porte UNIQUEMENT sur la part « service de livraison »,
      PAS sur la part repas. La colonne `apres_ci` de la grille EST la valeur
      réelle du reste à charge unitaire (apres_ci = ttc - service_ttc/2) ;
    * `total_apres_ci` = Σ (q × apres_ci) sur les lignes éligibles, et NON
      50 % du total. (L'ancienne règle « 50 % du total » du §7 était fausse.)
    * une ligne SANS `apres_ci` (ex. le Pain) : aucun crédit, comptée plein
      tarif dans le reste à charge, et remontée dans `avertissements`
      (« à vérifier » — éligibilité métier en attente de confirmation).
- Ventilation repas / service : une ligne n'est ventilée que si la grille
  fournit À LA FOIS `repas_*` et `service_*`. Les prestations sans
  ventilation (Pain, Ménage, Téléassistance, etc.) s'affichent en total
  simple et n'entrent pas dans les sommes repas/service.

Ce module n'a AUCUNE dépendance externe (stdlib seulement) afin que le test
du cas de référence (§7) tourne sans rien installer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Optional

# Nombre de semaines par mois retenu par la franchise (52 semaines / 12 mois).
SEMAINES_PAR_MOIS = Decimal(52) / Decimal(12)
DEUX_DEC = Decimal("0.01")


# --------------------------------------------------------------------------- #
# Modèle de données
# --------------------------------------------------------------------------- #
def _to_dec(valeur) -> Optional[Decimal]:
    """Convertit une valeur JSON (float/int/None) en Decimal exact via str."""
    if valeur is None:
        return None
    return Decimal(str(valeur))


@dataclass(frozen=True)
class Formule:
    """Une entrée de la grille tarifaire (tarifs.json), montants unitaires."""

    nom: str
    ttc: Decimal
    ht: Decimal
    apres_ci: Optional[Decimal]
    service_ttc: Optional[Decimal]
    service_ht: Optional[Decimal]
    repas_ttc: Optional[Decimal]
    repas_ht: Optional[Decimal]

    @property
    def ventilable(self) -> bool:
        """Vrai si la formule a une décomposition repas + service exploitable."""
        return self.repas_ttc is not None and self.service_ttc is not None

    @property
    def eligible_credit_impot(self) -> bool:
        """Vrai si la grille renseigne un tarif après crédit d'impôt."""
        return self.apres_ci is not None

    @classmethod
    def from_dict(cls, d: dict) -> "Formule":
        return cls(
            nom=d["formule"],
            ttc=_to_dec(d["ttc"]),
            ht=_to_dec(d["ht"]),
            apres_ci=_to_dec(d.get("apres_ci")),
            service_ttc=_to_dec(d.get("service_ttc")),
            service_ht=_to_dec(d.get("service_ht")),
            repas_ttc=_to_dec(d.get("repas_ttc")),
            repas_ht=_to_dec(d.get("repas_ht")),
        )


@dataclass
class LigneCalcul:
    """Résultat consolidé d'une ligne de saisie (formule × quantité)."""

    formule: Formule
    quantite: int  # nb de repas / semaine (ou quantité hebdo pour un service)

    # totaux hebdomadaires de la ligne
    total_ttc: Decimal = field(init=False)
    total_ht: Decimal = field(init=False)
    repas_ttc: Optional[Decimal] = field(init=False)
    repas_ht: Optional[Decimal] = field(init=False)
    service_ttc: Optional[Decimal] = field(init=False)
    service_ht: Optional[Decimal] = field(init=False)
    # Reste à charge hebdo après crédit d'impôt (None si ligne non éligible).
    apres_ci_total: Optional[Decimal] = field(init=False)

    def __post_init__(self) -> None:
        q = Decimal(self.quantite)
        f = self.formule
        self.total_ttc = q * f.ttc
        self.total_ht = q * f.ht
        if f.ventilable:
            self.repas_ttc = q * f.repas_ttc
            self.repas_ht = q * f.repas_ht
            self.service_ttc = q * f.service_ttc
            self.service_ht = q * f.service_ht
        else:
            self.repas_ttc = self.repas_ht = None
            self.service_ttc = self.service_ht = None
        # apres_ci de la grille = reste à charge unitaire (ttc - service_ttc/2).
        self.apres_ci_total = q * f.apres_ci if f.eligible_credit_impot else None


@dataclass
class Resultat:
    """Devis consolidé pour un ensemble de lignes de saisie."""

    lignes: list[LigneCalcul]

    total_hebdo_ttc: Decimal
    total_hebdo_ht: Decimal
    total_repas_ttc: Decimal
    total_repas_ht: Decimal
    total_service_ttc: Decimal
    total_service_ht: Decimal

    cout_mensuel_ttc: Decimal
    credit_impot_mensuel: Decimal  # montant du crédit (50 % du mensuel éligible)
    total_apres_ci: Decimal        # mensuel effectivement payé après crédit

    nb_repas_total: int
    avertissements: list[str]


# --------------------------------------------------------------------------- #
# Chargement de la grille
# --------------------------------------------------------------------------- #
def charger_grille(chemin: str | Path) -> dict[str, Formule]:
    """Charge tarifs.json et retourne un dict {nom_formule: Formule}."""
    # utf-8-sig : tolère un BOM (tarifs.json peut être édité/remplacé à la main).
    data = json.loads(Path(chemin).read_text(encoding="utf-8-sig"))
    return {e["formule"]: Formule.from_dict(e) for e in data}


# --------------------------------------------------------------------------- #
# Moteur
# --------------------------------------------------------------------------- #
def calculer(
    saisie: list[tuple[str, int]] | list[dict],
    grille: dict[str, Formule],
) -> Resultat:
    """Calcule un devis consolidé.

    `saisie` : liste de (nom_formule, quantite) ou de
               {"formule": ..., "nb_repas_semaine": ...}.
    `grille` : dict issu de `charger_grille`.
    """
    lignes: list[LigneCalcul] = []
    avertissements: list[str] = []

    for item in saisie:
        if isinstance(item, dict):
            nom = item["formule"]
            quantite = int(item.get("nb_repas_semaine", item.get("quantite")))
        else:
            nom, quantite = item
            quantite = int(quantite)

        if nom not in grille:
            raise KeyError(f"Formule absente de la grille tarifaire : {nom!r}")
        lignes.append(LigneCalcul(grille[nom], quantite))

    z = Decimal(0)
    total_hebdo_ttc = sum((l.total_ttc for l in lignes), z)
    total_hebdo_ht = sum((l.total_ht for l in lignes), z)
    total_repas_ttc = sum((l.repas_ttc for l in lignes if l.repas_ttc is not None), z)
    total_repas_ht = sum((l.repas_ht for l in lignes if l.repas_ht is not None), z)
    total_service_ttc = sum((l.service_ttc for l in lignes if l.service_ttc is not None), z)
    total_service_ht = sum((l.service_ht for l in lignes if l.service_ht is not None), z)

    cout_mensuel_ttc = total_hebdo_ttc * SEMAINES_PAR_MOIS

    # Crédit d'impôt 50 % : il porte UNIQUEMENT sur la part « service de
    # livraison », pas sur la part repas. La grille fournit déjà le reste à
    # charge unitaire dans la colonne `apres_ci` (= ttc - service_ttc/2).
    # => reste à charge = Σ (q × apres_ci) sur les lignes éligibles ;
    #    les lignes sans apres_ci (ex. Pain) sont comptées PLEIN TARIF.
    hebdo_apres_ci = z
    for l in lignes:
        if l.apres_ci_total is not None:
            hebdo_apres_ci += l.apres_ci_total
        else:
            hebdo_apres_ci += l.total_ttc  # non éligible → aucun crédit
    total_apres_ci = hebdo_apres_ci * SEMAINES_PAR_MOIS
    credit_impot_mensuel = cout_mensuel_ttc - total_apres_ci

    # Lignes à l'éligibilité indéterminée : on ne tranche pas, on signale.
    for l in lignes:
        if not l.formule.eligible_credit_impot:
            avertissements.append(
                f"« {l.formule.nom} » : crédit d'impôt à vérifier "
                f"(aucun tarif après crédit d'impôt dans la grille) — "
                f"non inclus dans le crédit calculé."
            )

    return Resultat(
        lignes=lignes,
        total_hebdo_ttc=total_hebdo_ttc,
        total_hebdo_ht=total_hebdo_ht,
        total_repas_ttc=total_repas_ttc,
        total_repas_ht=total_repas_ht,
        total_service_ttc=total_service_ttc,
        total_service_ht=total_service_ht,
        cout_mensuel_ttc=cout_mensuel_ttc,
        credit_impot_mensuel=credit_impot_mensuel,
        total_apres_ci=total_apres_ci,
        nb_repas_total=sum(l.quantite for l in lignes),
        avertissements=avertissements,
    )


# --------------------------------------------------------------------------- #
# Formatage d'affichage (français)
# --------------------------------------------------------------------------- #
def arrondi(valeur: Decimal) -> Decimal:
    """Arrondit à 2 décimales (demi vers le haut) — UNIQUEMENT pour l'affichage."""
    return valeur.quantize(DEUX_DEC, rounding=ROUND_HALF_UP)


def fmt_num(valeur: Decimal) -> str:
    """Formate un nombre a la francaise SANS symbole EUR.

    Utile quand la trame Word porte deja EUR / Euros HT : on ne remplit
    alors que le nombre, sans dupliquer le symbole monetaire.
    """
    q = arrondi(valeur)
    s = f"{q:,.2f}"  # 1,234.56
    return s.replace(",", " ").replace(".", ",")


def fmt_eur(valeur: Decimal) -> str:
    """Formate un montant a la francaise avec espace insecable et EUR."""
    return f"{fmt_num(valeur)} €"
