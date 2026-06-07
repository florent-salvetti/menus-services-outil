"""Génère deux CPV de TEST (T1 et T2) pour vérification visuelle.

Lance depuis la racine : python tests/generer_conditions_test.py
Sortie : dossiers/_TEST_conditions/  (ignoré par Git)

Mêmes données tarifaires que le cas de référence du devis
(Menus du marché 4C ×6 + Menus du jour 5C ×4) → chiffres cohérents devis/CPV.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.calcul import calculer, charger_grille
from src.documents.conditions import (
    InfosConditions,
    construire_template,
    generer_conditions,
)

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "dossiers" / "_TEST_conditions"


def main() -> None:
    grille = charger_grille(RACINE / "tarifs.json")
    res = calculer([("Menus du marché 4C", 6), ("Menus du jour 5C", 4)], grille)
    print(f"Tarif réinjecté : hebdo={res.total_hebdo_ttc:.2f} TTC / {res.total_hebdo_ht:.2f} HT "
          f"| repas={res.total_repas_ttc:.2f} | service={res.total_service_ttc:.2f}")

    # --- Cas T1 (tournée Lun/Jeu) -------------------------------------------
    construire_template("T1")
    infos_t1 = InfosConditions(
        client_nom="MARTIN Jeanne",
        client_adresse="12 rue des Lilas, 84100 Orange",
        benef_nom="MARTIN",
        benef_prenom="Jean",
        benef_adresse="12 rue des Lilas, 84100 Orange",
        lieu_prestation="",
        commencement="attendre",
        date_premiere_livraison="",
        jours_repas=["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"],
        lieu="Orange",
        date="07/06/2026",
    )
    out1 = generer_conditions("T1", infos_t1, res, SORTIE / "conditions_T1_test.docx")
    print(f"  -> {out1.relative_to(RACINE)} (commencement=attendre, jours Lun-Ven)")

    # --- Cas T2 (tournée Mar/Ven) -------------------------------------------
    construire_template("T2")
    infos_t2 = InfosConditions(
        client_nom="DURAND Paul",
        client_adresse="3 avenue de la Gare, 84100 Orange",
        benef_nom="DURAND",
        benef_prenom="Paul",
        benef_adresse="3 avenue de la Gare, 84100 Orange",
        lieu_prestation="Maison de retraite Les Oliviers, 84100 Orange",
        commencement="avant",
        date_premiere_livraison="20/06/2026",
        jours_repas=["Mardi", "Vendredi", "Samedi"],
        lieu="Orange",
        date="07/06/2026",
    )
    out2 = generer_conditions("T2", infos_t2, res, SORTIE / "conditions_T2_test.docx")
    print(f"  -> {out2.relative_to(RACINE)} (commencement=avant, jours Mar/Ven/Sam)")


if __name__ == "__main__":
    main()
