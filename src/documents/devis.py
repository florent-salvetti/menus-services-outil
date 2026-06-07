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
RACINE = Path(__file__).resolve().parent.parent.parent
MODELE_ORIGINAL = RACINE / "modeles" / "Trame devis.docx"
TEMPLATE_GENERE = RACINE / "modeles" / "_template_devis.docx"  # copie balisée

#: Index de paragraphe -> (label conservé, balises à coller après le label).
#: Le label reprend EXACTEMENT le texte de la trame (hors pointillés), suivi
#: de la/les balise(s). Les « € » / « Euros HT » de la trame sont préservés.
_PARA_REMPLACEMENTS = {
    2:  "{{ client_nom }}",
    3:  "{{ client_adresse }}",
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
    _rendre_conditionnel(para_beneficiaire, "beneficiaire")
    _rendre_conditionnel(para_lieu, "lieu_prestation")

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

    client_nom: str = ""
    client_adresse: str = ""
    devis_num: str = ""
    date_devis: str = ""
    date_validite: str = ""
    beneficiaire: str = ""
    lieu_prestation: str = ""


def _detail_repas(resultat: Resultat) -> str:
    """« 6 + 4 = 10 repas » (multi) ou « 6 repas » (mono)."""
    quantites = [l.quantite for l in resultat.lignes]
    if len(quantites) > 1:
        somme = " + ".join(str(q) for q in quantites)
        return f"{somme} = {resultat.nb_repas_total} repas"
    return f"{resultat.nb_repas_total} repas"


def _detail_formules(resultat: Resultat) -> str:
    """« Menus du marché 4C (×6) + Menus du jour 5C (×4) »."""
    return " + ".join(
        f"{l.formule.nom} (×{l.quantite})" for l in resultat.lignes
    )


def contexte_devis(resultat: Resultat, infos: InfosDevis) -> dict:
    """Construit le dict de rendu docxtpl à partir du résultat de calcul."""
    # Lignes optionnelles : vides si identiques au client → masquées au rendu.
    beneficiaire = infos.beneficiaire.strip()
    if beneficiaire and beneficiaire == infos.client_nom.strip():
        beneficiaire = ""
    lieu_prestation = infos.lieu_prestation.strip()
    if lieu_prestation and lieu_prestation == infos.client_adresse.strip():
        lieu_prestation = ""

    return {
        # champs non tarifaires
        "client_nom": infos.client_nom,
        "client_adresse": infos.client_adresse,
        "devis_num": infos.devis_num,
        "date_devis": infos.date_devis,
        "date_validite": infos.date_validite,
        "beneficiaire": beneficiaire,
        "lieu_prestation": lieu_prestation,
        # détail multi-formules (§6)
        "nb_repas_detail": _detail_repas(resultat),
        "formule_detail": _detail_formules(resultat),
        # totaux consolidés (nombres seuls, la trame porte « € » / « Euros HT »)
        "tarif_ttc": fmt_num(resultat.total_hebdo_ttc),
        "tarif_ht": fmt_num(resultat.total_hebdo_ht),
        "repas_ttc": fmt_num(resultat.total_repas_ttc),
        "repas_ht": fmt_num(resultat.total_repas_ht),
        "service_ttc": fmt_num(resultat.total_service_ttc),
        "service_ht": fmt_num(resultat.total_service_ht),
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
