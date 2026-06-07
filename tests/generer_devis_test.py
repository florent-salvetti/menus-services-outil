"""Génère des devis de TEST (données en dur) pour vérification visuelle.

Lance depuis la racine du projet : python tests/generer_devis_test.py
Sortie : dossiers/_TEST_devis/  (dossier ignoré par Git)
"""

import sys
from pathlib import Path

# Permet l'import de `src` même lancé directement (python tests/...).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.calcul import calculer, charger_grille
from src.documents.devis import (
    InfosDevis,
    construire_template,
    generer_devis,
)

# Racine du projet (ce script vit dans tests/, donc parent.parent).
RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "dossiers" / "_TEST_devis"


def main() -> None:
    grille = charger_grille(RACINE / "tarifs.json")

    # (Re)construit la copie-template balisée à partir de l'original.
    tpl = construire_template()
    print(f"Template balisé (re)généré : {tpl.relative_to(RACINE)}")

    # --- Cas 1 : cas de référence §6/§7 (multi-formules) ---------------------
    res1 = calculer(
        [("Menus du marché 4C", 6), ("Menus du jour 5C", 4)], grille
    )
    infos1 = InfosDevis(
        client_nom="Mme Jeanne MARTIN",
        client_adresse="12 rue des Lilas, 84100 Orange",
        devis_num="2026-0001",
        date_devis="07/06/2026",
        date_validite="07/07/2026",
        beneficiaire="M. Jean MARTIN",
        lieu_prestation="",
    )
    out1 = generer_devis(res1, infos1, SORTIE / "devis_reference_multi.docx")
    print(f"  -> {out1.relative_to(RACINE)}")
    print(f"     hebdo={res1.total_hebdo_ttc:.2f} mensuel={res1.cout_mensuel_ttc:.2f} "
          f"reste_a_charge={res1.total_apres_ci:.2f}")

    # --- Cas 2 : mono-formule -----------------------------------------------
    res2 = calculer([("Menus du marché 4C", 6)], grille)
    infos2 = InfosDevis(
        client_nom="M. Paul DURAND",
        client_adresse="3 avenue de la Gare, 84100 Orange",
        devis_num="2026-0002",
        date_devis="07/06/2026",
        date_validite="07/07/2026",
    )
    out2 = generer_devis(res2, infos2, SORTIE / "devis_mono_formule.docx")
    print(f"  -> {out2.relative_to(RACINE)}")
    print(f"     hebdo={res2.total_hebdo_ttc:.2f} mensuel={res2.cout_mensuel_ttc:.2f} "
          f"reste_a_charge={res2.total_apres_ci:.2f}")


if __name__ == "__main__":
    main()
