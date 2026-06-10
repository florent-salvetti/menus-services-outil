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
    categorie: str = "repas"  # "repas" | "supplement" | "service" (cf. tarifs.json)

    @property
    def est_repas(self) -> bool:
        """Vrai si c'est un vrai repas (compté dans « Nombre de repas »).

        Les suppléments (Potage, garniture, PQS, Pain…) et les prestations de
        service (Ménage, Téléassistance…) NE sont PAS des repas : ils restent
        dans les totaux du devis mais ne sont ni comptés ni listés comme repas
        (demande client). Une formule sans `categorie` est traitée en repas
        (compat. ascendante des anciennes grilles).
        """
        return self.categorie == "repas"

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
            categorie=d.get("categorie", "repas"),
        )


@dataclass
class LigneCalcul:
    """Résultat consolidé d'une ligne de saisie (formule × quantité)."""

    formule: Formule
    quantite: int  # nb de repas / semaine (ou quantité hebdo pour un service)
    regime: str = ""  # régime particulier ("diabétique", "sans sel", "mixé") — sans effet tarifaire

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


@dataclass(frozen=True)
class Remise:
    """Réduction commerciale optionnelle appliquée au devis.

    mode : "pourcent" (valeur = % du total hebdo TTC) ou "euros"
           (valeur = montant TTC déduit par semaine).
    La remise est répartie PROPORTIONNELLEMENT sur toutes les composantes
    (HT, parts repas/service, reste à charge après crédit d'impôt) afin que
    les invariants de la grille restent vrais (repas + service = total, et
    crédit d'impôt = 50 % de la part service).
    """

    mode: str
    valeur: Decimal


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

    # Réduction commerciale (montants APRÈS remise dans les champs ci-dessus).
    remise: Optional[Remise] = None
    remise_hebdo_ttc: Decimal = Decimal(0)   # montant TTC déduit / semaine
    prix_public_hebdo_ttc: Decimal = Decimal(0)  # total hebdo TTC avant remise


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
    remise: Optional[Remise] = None,
) -> Resultat:
    """Calcule un devis consolidé.

    `saisie` : liste de (nom_formule, quantite) ou de
               {"formule": ..., "nb_repas_semaine": ...}.
    `grille` : dict issu de `charger_grille`.
    `remise` : réduction commerciale optionnelle (cf. Remise) ; les totaux
               retournés sont APRÈS remise, le prix public est conservé dans
               `prix_public_hebdo_ttc`.
    """
    lignes: list[LigneCalcul] = []
    avertissements: list[str] = []

    for item in saisie:
        regime = ""
        if isinstance(item, dict):
            nom = item["formule"]
            quantite = int(item.get("nb_repas_semaine", item.get("quantite")))
            regime = item.get("regime", "")
        elif len(item) == 3:
            nom, quantite, regime = item
            quantite = int(quantite)
        else:
            nom, quantite = item
            quantite = int(quantite)

        if nom not in grille:
            raise KeyError(f"Formule absente de la grille tarifaire : {nom!r}")
        lignes.append(LigneCalcul(grille[nom], quantite, regime=regime))

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

    # --- Réduction commerciale (optionnelle) --------------------------------
    # Répartie au prorata sur TOUTES les composantes : les invariants
    # (repas + service = total ; crédit = 50 % du service) restent vrais.
    prix_public_hebdo_ttc = total_hebdo_ttc
    remise_hebdo_ttc = z
    if remise is not None and remise.valeur > 0 and total_hebdo_ttc > 0:
        if remise.mode == "pourcent":
            montant = total_hebdo_ttc * remise.valeur / Decimal(100)
        elif remise.mode == "euros":
            montant = remise.valeur
        else:
            raise ValueError(f"Mode de remise inconnu : {remise.mode!r}")
        if montant > total_hebdo_ttc:
            montant = total_hebdo_ttc
            avertissements.append(
                "Remise plafonnée au total du devis (elle dépassait le montant hebdomadaire)."
            )
        remise_hebdo_ttc = montant
        ratio = (total_hebdo_ttc - montant) / total_hebdo_ttc
        total_hebdo_ttc *= ratio
        total_hebdo_ht *= ratio
        total_repas_ttc *= ratio
        total_repas_ht *= ratio
        total_service_ttc *= ratio
        total_service_ht *= ratio
        cout_mensuel_ttc *= ratio
        total_apres_ci *= ratio
        credit_impot_mensuel = cout_mensuel_ttc - total_apres_ci

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
        nb_repas_total=sum(l.quantite for l in lignes if l.formule.est_repas),
        avertissements=avertissements,
        remise=remise if remise_hebdo_ttc > 0 else None,
        remise_hebdo_ttc=remise_hebdo_ttc,
        prix_public_hebdo_ttc=prix_public_hebdo_ttc,
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
