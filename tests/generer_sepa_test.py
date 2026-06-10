"""Génère un mandat SEPA de TEST (IBAN fictif valide) pour vérification visuelle.

Lance depuis la racine : python tests/generer_sepa_test.py
Sortie : dossiers/_TEST_sepa/  (ignoré par Git)

⚠️ IBAN/BIC fictifs, jamais persistés (RGPD §9).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.iban import IbanInvalide, formater_affichage, generer_iban_fr
from src.documents.sepa import InfosMandat, construire_template, generer_mandat

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "dossiers" / "_TEST_sepa"


def main() -> None:
    tpl = construire_template()
    print(f"Template balisé (re)généré : {tpl.relative_to(RACINE)}")

    # IBAN FR fictif mais VALIDE (clés RIB + IBAN calculées).
    iban = generer_iban_fr("30004", "00001", "00001234567")
    bic = "BNPAFRPPXXX"
    print(f"IBAN de test : {formater_affichage(iban)}  (BIC {bic})")

    infos = InfosMandat(
        debiteur_nom="Mme Jeanne MARTIN",
        debiteur_adresse="12 rue des Lilas, 84100 Orange",
        banque_nom="BNP Paribas",
        banque_adresse="5 place de la République, 84100 Orange",
        lieu_signature="Orange",
        date_signature="07/06/2026",
    )

    out = generer_mandat(infos, iban, bic, SORTIE / "mandat_sepa_test.docx")
    print(f"  -> {out.relative_to(RACINE)}")

    # Flux nominal de l'app (demande client) : SANS coordonnées bancaires —
    # les cases restent vides, le client joint son RIB.
    infos_vide = InfosMandat(
        debiteur_nom="Mme Jeanne MARTIN",
        debiteur_adresse="12 rue des Lilas, 84100 Orange",
        lieu_signature="Orange",
        date_signature="07/06/2026",
    )
    out2 = generer_mandat(infos_vide, None, "", SORTIE / "mandat_sans_rib_test.docx")
    print(f"  -> {out2.relative_to(RACINE)} (cases bancaires vides)")

    # Contrôle : un IBAN invalide doit REFUSER la génération.
    iban_casse = "FR1520041010050500013M02606"  # clé mod 97 fausse
    try:
        generer_mandat(infos, iban_casse, bic, SORTIE / "NE_DOIT_PAS_EXISTER.docx")
        print("  !! ERREUR : la génération aurait dû être refusée")
    except IbanInvalide as e:
        print(f"  Refus correct sur IBAN invalide : {e}")


if __name__ == "__main__":
    main()
