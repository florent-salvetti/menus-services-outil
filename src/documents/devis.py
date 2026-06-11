"""Génération du devis Les Menus Services.

Principe (CLAUDE.md §5, §11) :
- On ne TOUCHE JAMAIS l'original `modeles/Trame devis.docx`.
- On construit une COPIE-TEMPLATE où les pointillés « ……… » de la trame sont
  remplacés par des balises Jinja `{{ }}` (docxtpl), SANS modifier le texte
  réglementaire ni la mise en page : on conserve le label de chaque ligne et
  les symboles « € » / « Euros HT » déjà présents ; on n'injecte que la valeur.
- docxtpl rend ensuite le template avec le contexte calculé par src.calcul.

Le rendu multi-formules suit le §6 :
- « Nombre de repas » et « Formule choisie » montrent le détail par formule ;
- les lignes de tarif portent les totaux consolidés ;
- la 2e ligne du tableau porte le reste à charge après crédit d'impôt.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from docx import Document
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph
from docxtpl import DocxTemplate

from src.calcul import Resultat, fmt_num

# Emplacement des fichiers
from src.chemins import RACINE
MODELE_ORIGINAL = RACINE / "modeles" / "Trame devis.docx"
TEMPLATE_GENERE = RACINE / "modeles" / "_template_devis.docx"  # copie balisée

#: Index de paragraphe -> (label conservé, balises à coller après le label).
#: Le label reprend EXACTEMENT le texte de la trame (hors pointillés), suivi
#: de la/les balise(s). Les « € » / « Euros HT » de la trame sont préservés.
_PARA_REMPLACEMENTS = {
    # En-tête coordonnées — révision client 11/06/2026 :
    # « M./Mme NOM Prénom » sur UNE ligne, puis l'adresse, puis « CP Ville ».
    1:  "{{ client_identite }}",
    2:  "{{ client_rue }}",
    3:  "{{ client_cp_ville }}",
    4:  "Devis N° {{ devis_num }}",
    5:  "Date de devis : {{ date_devis }}",
    6:  "Date de validité : {{ date_validite }}",
    7:  "Prénom NOM du bénéficiaire des prestations si différent du client : {{ beneficiaire }}",
    8:  "Lieu de la prestation si différent de l’adresse du client : {{ lieu_prestation }}",
    12: "Nombre de repas par semaine : {{ nb_repas_detail }}",
    13: "Formule choisie : {{ formule_detail }}",
    14: "Tarif de la formule de repas choisie : {{ tarif_ttc }} € TTC ({{ tarif_ht }} Euros HT)",
    # NB : la trame originale écrit « €TTC » sans espace (incohérent avec les
    # autres lignes). Correction validée par le client → « € TTC ».
    15: "- dont Prix du repas {{ repas_ttc }} € TTC (TVA 10% - {{ repas_ht }} Euros HT)",
    16: "- dont prix du Service de livraison d’un repas {{ service_ttc }} € TTC (TVA 10% - {{ service_ht }} Euros HT)",
    17: "Devis pour 1 semaine : {{ hebdo_ttc }} € TTC.",
    18: "Coût mensuel moyen : {{ mensuel_ttc }} € TTC (calculé en multipliant le total hebdomadaire x 52/12).",
}


# --------------------------------------------------------------------------- #
# Construction de la copie-template balisée
# --------------------------------------------------------------------------- #
def _ecrire_paragraphe(paragraphe, texte: str) -> None:
    """Réécrit le texte d'un paragraphe en conservant la mise en forme.

    On garde la police du 1er run existant, et on supprime les runs suivants —
    le style du paragraphe (alignement, interligne) est inchangé.
    """
    runs = paragraphe.runs
    if not runs:
        paragraphe.add_run(texte)
        return
    runs[0].text = texte
    for r in runs[1:]:
        r.text = ""


def _nouveau_paragraphe(ancre: Paragraph, texte: str, *, avant: bool) -> Paragraph:
    """Insère un paragraphe (texte brut) juste avant/après `ancre`."""
    p = OxmlElement("w:p")
    if avant:
        ancre._p.addprevious(p)
    else:
        ancre._p.addnext(p)
    para = Paragraph(p, ancre._parent)
    para.add_run(texte)
    return para


def _nouveau_paragraphe_meme_police(ancre: Paragraph, texte: str) -> Paragraph:
    """Insère après `ancre` un paragraphe reprenant la police de son 1er run."""
    para = _nouveau_paragraphe(ancre, texte, avant=False)
    if ancre.runs and para.runs:
        src, dst = ancre.runs[0].font, para.runs[0].font
        dst.name = src.name
        dst.size = src.size
    return para


def _rendre_conditionnel(paragraphe: Paragraph, condition: str) -> None:
    """Entoure un paragraphe de balises docxtpl `{%p if %}` / `{%p endif %}`.

    Le paragraphe entier DISPARAÎT si `condition` est fausse (vide) au rendu ;
    les paragraphes if/endif sont eux-mêmes supprimés par docxtpl. La mise en
    forme du paragraphe d'origine est intacte quand il est conservé.
    """
    _nouveau_paragraphe(paragraphe, f"{{%p if {condition} %}}", avant=True)
    _nouveau_paragraphe(paragraphe, "{%p endif %}", avant=False)


def construire_template(
    src: Path = MODELE_ORIGINAL, dst: Path = TEMPLATE_GENERE
) -> Path:
    """Crée (ou recrée) la copie-template balisée à partir de l'original."""
    doc = Document(str(src))

    for idx, texte in _PARA_REMPLACEMENTS.items():
        _ecrire_paragraphe(doc.paragraphs[idx], texte)

    # Lignes optionnelles : on capture les paragraphes AVANT toute insertion
    # (les références restent valides), puis on les rend conditionnels.
    # Vides => le paragraphe entier disparaît (pas d'intitulé orphelin).
    para_beneficiaire = doc.paragraphs[7]
    para_lieu = doc.paragraphs[8]
    para_service = doc.paragraphs[16]  # « - dont prix du Service… »
    _rendre_conditionnel(para_beneficiaire, "beneficiaire")
    _rendre_conditionnel(para_lieu, "lieu_prestation")

    # Réduction commerciale : ligne ajoutée entre la décomposition du tarif et
    # « Devis pour 1 semaine », visible UNIQUEMENT quand une remise est saisie.
    para_remise = _nouveau_paragraphe_meme_police(
        para_service, "Remise commerciale : {{ remise_detail }}"
    )
    _rendre_conditionnel(para_remise, "remise_detail")

    # Tableau « Total mensuel TTC » / « Total après crédit d'impôt »
    tbl = doc.tables[0]
    _ecrire_paragraphe(tbl.rows[0].cells[1].paragraphs[0], "{{ mensuel_ttc }}  €")
    _ecrire_paragraphe(tbl.rows[1].cells[1].paragraphs[0], "{{ reste_a_charge }} €")

    doc.save(str(dst))
    return dst


# --------------------------------------------------------------------------- #
# Données de saisie (en attendant l'UI) + contexte de rendu
# --------------------------------------------------------------------------- #
@dataclass
class InfosDevis:
    """Champs non tarifaires du devis (alimentés par l'UI plus tard)."""

    civilite: str = ""        # « M. » ou « Mme »
    client_nom: str = ""      # « NOM Prénom » (+ mention tutelle éventuelle)
    client_rue: str = ""      # adresse (rue)
    client_cp_ville: str = "" # « CP Ville »
    devis_num: str = ""
    date_devis: str = ""
    date_validite: str = ""
    beneficiaire: str = ""
    lieu_prestation: str = ""


def _lignes_repas(resultat: Resultat) -> list:
    """Lignes qui sont de VRAIS repas (cf. catégorie de la grille).

    Suppléments (Potage, garniture, PQS, Pain…) et services (Ménage,
    Téléassistance…) sont exclus du décompte et de la liste « Formule
    choisie » : leur montant reste fondu dans les totaux du devis, mais ils
    n'apparaissent pas comme des repas (demande client 10/06/2026).
    """
    return [l for l in resultat.lignes if l.formule.est_repas]


def _detail_repas(resultat: Resultat) -> str:
    """« 6 + 4 = 10 repas » (multi) ou « 6 repas » (mono)."""
    quantites = [l.quantite for l in _lignes_repas(resultat)]
    if len(quantites) > 1:
        somme = " + ".join(str(q) for q in quantites)
        return f"{somme} = {resultat.nb_repas_total} repas"
    return f"{resultat.nb_repas_total} repas"


def _nom_ligne(ligne) -> str:
    """Nom de la prestation, suivi du régime particulier le cas échéant."""
    if ligne.regime.strip():
        return f"{ligne.formule.nom} – {ligne.regime.strip()}"
    return ligne.formule.nom


def _detail_formules(resultat: Resultat) -> str:
    """« Menus du marché 4C – diabétique (×6) + Menus du jour 5C (×4) ».

    Seuls les vrais repas sont listés (suppléments/services masqués ici).
    """
    return " + ".join(
        f"{_nom_ligne(l)} (×{l.quantite})" for l in _lignes_repas(resultat)
    )


def _join_unitaires(valeurs) -> str:
    """Joint des montants UNITAIRES par « / » (un par formule), « — » si aucun."""
    textes = [fmt_num(v) for v in valeurs if v is not None]
    return " / ".join(textes) if textes else "—"


def tarifs_unitaires(resultat: Resultat) -> dict:
    """Tarifs AU REPAS (unitaires, prix catalogue) pour devis et CPV.

    Demande client : les lignes « Tarif de la formule », « dont Prix du
    repas » et « dont prix du Service » affichent le tarif d'UN repas, pas le
    total hebdomadaire. Multi-formules : un montant par formule, séparés par
    « / », dans l'ordre de la ligne « Formule choisie ».
    """
    lignes = _lignes_repas(resultat)  # alignées sur « Formule choisie »
    return {
        "tarif_ttc": _join_unitaires(l.formule.ttc for l in lignes),
        "tarif_ht": _join_unitaires(l.formule.ht for l in lignes),
        "repas_ttc": _join_unitaires(l.formule.repas_ttc for l in lignes),
        "repas_ht": _join_unitaires(l.formule.repas_ht for l in lignes),
        "service_ttc": _join_unitaires(l.formule.service_ttc for l in lignes),
        "service_ht": _join_unitaires(l.formule.service_ht for l in lignes),
    }


def _detail_remise(resultat: Resultat) -> str:
    """Texte de la ligne « Remise commerciale », vide si aucune remise.

    Ex. « - 5 % soit - 6,54 € TTC / semaine (prix public : 130,80 € TTC / semaine) ».
    Les montants affichés sur le devis sont déjà APRÈS remise (cf. calcul).
    """
    if resultat.remise is None or resultat.remise_hebdo_ttc <= 0:
        return ""
    public = f"(prix public : {fmt_num(resultat.prix_public_hebdo_ttc)} € TTC / semaine)"
    montant = f"- {fmt_num(resultat.remise_hebdo_ttc)} € TTC / semaine"
    if resultat.remise.mode == "pourcent":
        pct = f"{fmt_num(resultat.remise.valeur)}".removesuffix(",00")
        return f"- {pct} % soit {montant.lstrip('- ')} {public}"
    return f"{montant} {public}"


def contexte_devis(resultat: Resultat, infos: InfosDevis) -> dict:
    """Construit le dict de rendu docxtpl à partir du résultat de calcul."""
    # Lignes optionnelles : vides si identiques au client → masquées au rendu.
    beneficiaire = infos.beneficiaire.strip()
    if beneficiaire and beneficiaire == infos.client_nom.strip():
        beneficiaire = ""
    client_adresse = ", ".join(
        x for x in (infos.client_rue.strip(), infos.client_cp_ville.strip()) if x
    )
    lieu_prestation = infos.lieu_prestation.strip()
    if lieu_prestation and lieu_prestation == client_adresse:
        lieu_prestation = ""

    # « M./Mme NOM Prénom » sur une ligne (la mention tutelle éventuelle de
    # client_nom passe à la ligne via le « \n » rendu par docxtpl).
    identite = " ".join(
        x for x in (infos.civilite.strip(), infos.client_nom.strip()) if x
    )

    return {
        # champs non tarifaires
        "client_identite": identite or "Monsieur / Madame",
        "client_rue": infos.client_rue,
        "client_cp_ville": infos.client_cp_ville,
        "devis_num": infos.devis_num,
        "date_devis": infos.date_devis,
        "date_validite": infos.date_validite,
        "beneficiaire": beneficiaire,
        "lieu_prestation": lieu_prestation,
        # détail multi-formules (§6)
        "nb_repas_detail": _detail_repas(resultat),
        "formule_detail": _detail_formules(resultat),
        # remise commerciale (ligne masquée si vide)
        "remise_detail": _detail_remise(resultat),
        # tarifs AU REPAS (unitaires — demande client), un montant par formule
        **tarifs_unitaires(resultat),
        # totaux hebdo / mensuels consolidés (après remise éventuelle)
        "hebdo_ttc": fmt_num(resultat.total_hebdo_ttc),
        "mensuel_ttc": fmt_num(resultat.cout_mensuel_ttc),
        "reste_a_charge": fmt_num(resultat.total_apres_ci),
    }


def generer_devis(
    resultat: Resultat,
    infos: InfosDevis,
    sortie: Path,
    template: Optional[Path] = None,
) -> Path:
    """Génère un devis .docx rempli dans `sortie`.

    Reconstruit la copie-template balisée si elle n'existe pas encore.
    """
    if template is None:
        template = TEMPLATE_GENERE
    if not Path(template).exists():
        construire_template(dst=Path(template))

    tpl = DocxTemplate(str(template))
    tpl.render(contexte_devis(resultat, infos))
    sortie.parent.mkdir(parents=True, exist_ok=True)
    tpl.save(str(sortie))
    return sortie
