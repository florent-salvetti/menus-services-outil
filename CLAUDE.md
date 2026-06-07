# CLAUDE.md — Générateur de documents Les Menus Services Orange

Fichier de cadrage pour Claude Code. À lire en entier avant de générer du code.

---

## 1. Objectif du projet

Outil de bureau **portable** (un dossier qu'on copie sur le PC et qui fonctionne directement, sans installation) qui, à partir d'une **saisie unique** des informations d'un nouveau bénéficiaire, génère automatiquement les documents d'ouverture de dossier d'une agence de portage de repas à domicile (franchise Les Menus Services — entité juridique SAS BON A DOM', Orange).

Le traitement des données est **local** (rien n'est envoyé sur un cloud). **Seule exception réseau : la vérification de licence au démarrage** (cf. §15). L'OCR du RIB tourne en local.

Aujourd'hui ces documents sont remplis **à la main** sur des trames Word. L'outil supprime la ressaisie et fiabilise les calculs tarifaires.

**Client final / utilisateur unique de cette première version : Michaël Vasnier** (agence d'Orange). L'outil doit rester généralisable à d'autres agences plus tard (cf. §10).

---

## 2. Contraintes non négociables

1. **Portable.** L'app fonctionne en copiant un seul dossier sur le PC, sans installation, et tourne directement depuis ce dossier (exécutable + ressources + données dans le même répertoire). Chemins relatifs uniquement, aucune dépendance à une installation système.
2. **Traitement local.** Les données (bénéficiaires, documents) restent sur le poste. Pas de cloud, pas de télémétrie. **Seul appel réseau autorisé : la vérification de licence au démarrage** (§15). L'OCR du RIB tourne en local.
3. **Ne touche pas au CRM** (Ximi / logiciel métier de l'agence). L'outil ne lit ni n'écrit dans le CRM. Aucune intégration, aucune automatisation de navigateur sur le CRM. La donnée entre uniquement par saisie manuelle dans l'outil.
4. **Données sensibles — IBAN non conservé.** Les bénéficiaires sont des personnes âgées (données personnelles + bancaires). Décisions prises pour cette version : **pas de chiffrement de la base locale** (risque assumé, cf. §3 RGPD), mais **l'IBAN n'est JAMAIS stocké de façon persistante** : il sert uniquement à générer le mandat SEPA en mémoire, puis est écarté. Il ne figure que dans le document généré, archivé par l'utilisateur. Prévoir aussi l'effacement d'un dossier.
5. **Fidélité aux documents officiels.** Les trames Word de la franchise ne doivent PAS être restructurées. L'outil remplit les champs prévus, sans modifier le texte réglementaire ni la mise en page. (cf. §6)
6. **Grille tarifaire externalisée.** Les tarifs changent (révisions périodiques). La grille doit être un fichier de données remplaçable (le `tarifs.json` fourni, ou relecture directe du `.xlsx`), JAMAIS codée en dur dans la logique. (cf. §5)

---

## 3. Flux utilisateur cible

```
1. SAISIE      → l'utilisateur remplit un formulaire unique (infos bénéficiaire,
                 client, formules + quantités, jours, tournée, RIB scanné)
2. GÉNÉRATION  → l'outil produit les documents remplis (devis, conditions
                 particulières T1 ou T2, mandat SEPA) + joint les CGV
3. RÉCAP       → l'outil affiche un récapitulatif propre et copiable, à reporter
                 manuellement dans le CRM par l'utilisateur (copier-coller)
```

L'étape 3 est volontairement un copier-coller manuel : l'outil ne pilote jamais le CRM.

> **Note RGPD (risque assumé).** La base locale n'est pas chiffrée dans cette version. Les données bénéficiaires (hors IBAN, non conservé) restent en clair dans le dossier de l'app. En cas de vol/copie du PC, ces données sont exposées ; la responsabilité de traitement incombe à l'agence. Ce choix est assumé pour cette version ; un chiffrement de la base pourra être ajouté ultérieurement sans refonte. Un **contrat de sous-traitance RGPD** entre le prestataire et l'agence doit être signé en parallèle (hors périmètre logiciel).

---

## 4. Documents à produire (périmètre validé sur fichiers réels)

| Document | Action de l'outil | Champs dynamiques ? |
|---|---|---|
| **Devis** (`Trame_devis`) | Remplir + calculer | OUI — cœur de la valeur |
| **Conditions Particulières de Vente T1** | Remplir la section finale | OUI |
| **Conditions Particulières de Vente T2** | Remplir la section finale | OUI |
| **Mandat de prélèvement SEPA** (`Autorisation_de_prélèvements`) | Remplir (IBAN via OCR) | OUI |
| **CGV** (`CGV_..._client`) | Joindre tel quel | NON (texte fixe) |

- **T1 vs T2** : déterminé par la **tournée (semaine paire / impaire)**. Ce n'est PAS qu'un titre : le tableau des jours de livraison diffère.
  - **T1** → jours de livraison **LUNDI et JEUDI**
  - **T2** → jours de livraison **MARDI et VENDREDI**
  - → l'interface a un sélecteur **Tournée : T1 / T2** qui choisit le bon modèle Word de base. Ne PAS reconstruire le tableau des jours : partir du bon modèle et remplir les trous.
- La section « coût des prestations » des Conditions reprend **les mêmes champs tarifaires** que le devis → calculés une fois, réinjectés dans les deux.

---

## 5. Grille tarifaire (donnée de référence)

Fournie en `tarifs.json` (à placer à côté de l'exécutable, rechargeable). Structure d'une entrée :

```json
{
  "formule": "Menus du marché 4C",
  "ttc": 12.8,            // tarif public TTC unitaire (par repas)
  "ht": 11.6364,          // tarif public HT unitaire
  "apres_ci": 9.612,      // tarif unitaire après crédit d'impôt 50%
  "service_ttc": 6.376,   // part SERVICE de livraison, TTC (TVA 10%)
  "service_ht": 5.7964,
  "repas_ttc": 6.424,     // part REPAS, TTC (TVA 10%)
  "repas_ht": 5.84
}
```

Invariant vérifié sur les données : `service_ttc + repas_ttc == ttc` (à l'arrondi près). Idem en HT.

Source : `TArifs_2026.xlsx`, feuille « Tarifs 26 », tarifs au 01/01/2026. 29 lignes (formules repas + suppléments + prestations de service horaires/mensuelles). Les prestations de service (ménage, téléassistance, etc.) n'ont pas de décomposition repas/service.

---

## 6. Trame de devis — remplissage logique multi-formules

**Cas à gérer :** un même devis peut comporter **plusieurs formules** (ex. un couple où chacun choisit différemment). Exemple réel : `Menus du marché 4C ×6 + Menus du jour 5C ×4`.

**Règle de remplissage :** garder la trame telle quelle. Le moteur calcule **ligne par ligne** en interne, puis écrit dans chaque champ existant le **résultat consolidé**, en faisant apparaître le détail des formules sur les deux premières lignes.

Rendu attendu pour l'exemple ci-dessus :

```
Nombre de repas par semaine : 6 + 4 = 10 repas
Formule choisie : Menus du marché 4C (×6) + Menus du jour 5C (×4)
Tarif de la formule de repas choisie : 130,80 € TTC (118,91 € HT)
   - dont Prix du repas : 65,91 € TTC (TVA 10% — 59,92 € HT)
   - dont prix du Service de livraison : 64,89 € TTC (TVA 10% — 58,99 € HT)
Devis pour 1 semaine : 130,80 € TTC
Coût mensuel moyen : 566,80 € TTC (130,80 × 52/12)
Total après crédit d'impôt : 283,40 €
```

Les lignes de tarif portent le **total consolidé** ; le détail des formules apparaît uniquement sur « Nombre de repas » et « Formule choisie ».

---

## 7. Moteur de calcul (spécification, valeurs vérifiées)

Entrée : liste de lignes `[{formule, nb_repas_semaine}, ...]`.

Pour chaque ligne, lire la formule dans la grille puis :
```
ligne.total_ttc      = nb_repas * ttc
ligne.total_ht       = nb_repas * ht
ligne.repas_ttc      = nb_repas * repas_ttc
ligne.repas_ht       = nb_repas * repas_ht
ligne.service_ttc    = nb_repas * service_ttc
ligne.service_ht     = nb_repas * service_ht
```
Consolidation (somme de toutes les lignes) :
```
total_hebdo_ttc      = Σ ligne.total_ttc
total_hebdo_ht       = Σ ligne.total_ht
total_repas_ttc      = Σ ligne.repas_ttc      (idem HT)
total_service_ttc    = Σ ligne.service_ttc    (idem HT)
cout_mensuel_ttc     = total_hebdo_ttc * 52 / 12
# Reste à charge après crédit d'impôt — cf. règle ci-dessous (PAS cout/2).
total_apres_ci       = (Σ ligne.nb_repas * apres_ci) [lignes éligibles] * 52 / 12
```

**Crédit d'impôt — règle exacte (vérifiée avec le client) :**
Le crédit d'impôt de 50 % porte **UNIQUEMENT sur la part « service de livraison »**, **pas** sur la part repas. La colonne `apres_ci` de la grille **EST** la valeur du reste à charge unitaire après crédit : `apres_ci = ttc - service_ttc / 2`.
- `total_apres_ci` (reste à charge mensuel) = `Σ (nb_repas × apres_ci)` sur les **lignes éligibles** (celles qui ont un `apres_ci`), `× 52 / 12`.
- Lignes **sans** `apres_ci` (ex. le Pain) : **aucun crédit**, comptées plein tarif dans le reste à charge, et **signalées « crédit d'impôt à vérifier »** (éligibilité métier en attente de confirmation).
- Les prestations de service (Ménage, Téléassistance, etc.) **ONT** un `apres_ci` → elles **sont** éligibles.

> ⚠️ **L'ancienne règle « `total_apres_ci = cout_mensuel_ttc / 2` (50 % du total) » était ERRONÉE** et a été corrigée. Le crédit ne s'applique jamais à la part repas.

**Cas de test de référence** (doit passer) :
`Menus du marché 4C ×6 + Menus du jour 5C ×4` →
- total_hebdo_ttc = 130,80 ; total_hebdo_ht = 118,91
- total_repas_ttc = 65,91 ; total_service_ttc = 64,89 (vérif : 65,91 + 64,89 = 130,80)
- cout_mensuel_ttc = 566,80
- **total_apres_ci (reste à charge mensuel) = 426,21** (= (6×9,612 + 4×10,171) × 52/12)
- **crédit d'impôt mensuel = 140,59** (= cout_mensuel_ttc − total_apres_ci = 50 % de la part service mensuelle)

**Arrondis :** calculer en pleine précision, n'arrondir qu'à l'affichage (2 décimales, séparateur décimal « , » français, « € » suffixé). Le plafond légal du crédit d'impôt (12 000–20 000 €/an selon situation) n'est pas géré par l'outil (mention informative déjà présente dans les documents).

---

## 8. Champs du formulaire de saisie

**Client (payeur / signataire)**
- Civilité (M./Mme), Prénom, NOM
- Adresse complète (rue, CP, ville)
- Téléphone, email (optionnels)

**Bénéficiaire des prestations** (si différent du client)
- Prénom NOM
- Lieu de la prestation (si différent de l'adresse client)

**Prestations — liste de lignes (1 à N)**
- Par ligne : Formule (liste déroulante depuis la grille) + Nb de repas / semaine
- Bouton « ajouter une formule »

**Modalités de livraison**
- Tournée : **T1** (Lun/Jeu) ou **T2** (Mar/Ven) → sélectionne le modèle de Conditions
- Jours de repas souhaités : cases Lundi → Dimanche
- Commencement : « après délai 14 j » OU « avant fin du délai de rétractation » + date 1re livraison

**Coordonnées bancaires (mandat SEPA)**
- Nom/adresse du débiteur (= client en général)
- Nom + adresse de l'établissement bancaire
- IBAN + BIC → **pré-remplis par OCR du RIB scanné**, avec **validation visuelle obligatoire** par l'utilisateur avant génération (une erreur d'IBAN = prélèvement rejeté). **Non stockés après génération** (cf. §9).

**Métadonnées devis**
- N° de devis (auto-incrément local), date du devis, date de validité, lieu (« Fait à … »)

---

## 9. OCR du RIB (local)

- Objectif : lire **IBAN** et **BIC** depuis un RIB scanné/photographié, pour pré-remplir le mandat SEPA.
- 100 % local (ex. Tesseract, ou modèle de vision local selon perfs machine).
- **L'IBAN lu est toujours soumis à validation humaine** dans l'UI avant génération. Afficher l'IBAN reconnu en grand, éditable.
- Validation de format : contrôle de la clé IBAN (mod 97) pour détecter une lecture erronée.
- **IBAN/BIC non persistés** : ils vivent uniquement en mémoire le temps de générer le mandat SEPA, puis sont écartés. Ne pas les écrire dans la base de dossiers. Ils ne subsistent que dans le document SEPA généré.
- **Supprimer l'image du RIB immédiatement après extraction** (ne pas la conserver dans le dossier).

---

## 10. Constantes émetteur (agence Orange — à externaliser dans un `config.json`)

À ne PAS coder en dur : ce sont les infos d'une agence donnée, variables d'une agence à l'autre.
```
Raison sociale : SAS BON A DOM'
Adresse : 341 rue d'Aquitaine, 84100 Orange
Tél : 04 90 70 37 06
Email : orange@les-menus-services.com
Capital : 10 000 €
RCS : 853 820 157 RCS Avignon
TVA intracom : FR10 853 820 157
Déclaration SAP : 853820157 du 12/11/2019
ICS (mandat SEPA) : FR18ZZZ86BB45
Représentant : VASNIER Michaël
```
Externaliser ces valeurs permet de revendre l'outil à une autre agence en changeant juste le `config.json` et les modèles Word.

---

## 11. Stack & génération de documents

- **Type d'app** : application de bureau **portable** (un dossier copiable, lancé directement, sans installation). **Cible : Windows** (PC de l'agence). Python est cohérent avec l'OCR ; packager avec **PyInstaller `--onedir`** (PAS `--onefile` : onefile se décompresse dans un dossier temporaire à chaque lancement, ce qui casse l'esprit « tout dans un dossier » et ralentit le démarrage). Compilation **sur Windows** (PyInstaller ne cross-compile pas). Tout (binaire, modèles, `config.json`, `tarifs.json`, base de dossiers) vit dans le dossier de l'app, en chemins relatifs.
- **Génération Word** : remplir les modèles `.docx` par substitution de champs (recommandé : `python-docx`, ou un moteur de templating type `docxtpl` avec des balises `{{ }}` insérées dans des copies des modèles). Conserver la mise en page d'origine.
- **Modèles** : travailler sur des **copies** des `.docx` officiels comme templates ; ne jamais écraser les originaux.
- **Sortie** : un dossier par bénéficiaire contenant les documents générés (docx + PDF). Nommage : `NOM_Prénom_AAAA-MM-JJ/`.
- **Impression groupée** : bouton « Tout imprimer » qui produit d'abord un **PDF unique fusionné** dans l'ordre logique (devis → conditions T1/T2 → mandat SEPA → CGV), puis l'envoie à l'imprimante par défaut. Le PDF fusionné est aussi conservé dans le dossier bénéficiaire (pratique pour archivage et signature). Préférer la fusion PDF à l'envoi de N fichiers séparés (ordre garanti, plus fiable).

---

## 12. Garde-fous (rappel)

- Ne pas connecter, lire ou écrire dans le CRM, sous aucune forme.
- Ne pas restructurer les documents réglementaires : remplissage des trous uniquement.
- Ne jamais coder les tarifs ni les infos agence en dur — fichiers de données.
- IBAN : validation humaine + contrôle clé mod 97 ; **jamais persisté** ; image RIB supprimée après lecture.
- App **portable**, chemins relatifs, aucune dépendance à une installation système.
- Seul appel réseau autorisé : la **vérification de licence** (§15). Aucune autre sortie réseau, pas de télémétrie.
- Prévoir l'effacement d'un dossier.
- **Pas de chiffrement de la base** dans cette version (risque assumé, décision client). Voir §3 RGPD pour la mention de ce risque.

---

## 13. Fichiers de référence fournis

- `TArifs_2026.xlsx` — grille tarifaire source (feuille « Tarifs 26 »)
- `tarifs.json` — grille extraite et nettoyée (29 formules) → donnée de l'app
- `Trame_devis.doc` — modèle de devis à remplir
- `Conditions_Particulieres_..._T1_....doc` — modèle conditions tournée T1 (Lun/Jeu)
- `Conditions_Particulieres_..._T2_....doc` — modèle conditions tournée T2 (Mar/Ven)
- `Autorisation_de_prélèvements.docx` — modèle mandat SEPA
- `CGV_..._client.doc` — CGV à joindre telles quelles

> Les `.doc` sont d'anciens formats Word binaires : les convertir en `.docx` (ex. LibreOffice headless) avant de les utiliser comme templates.

---

## 14. Ordre de construction suggéré

1. Charger `tarifs.json` + `config.json`.
2. Implémenter et **tester le moteur de calcul** sur le cas de référence du §7 (doit tomber exactement).
3. Formulaire de saisie (multi-lignes formules + sélecteur tournée).
4. Génération du **devis** (le plus de valeur).
5. Génération des **conditions** T1/T2 + **mandat SEPA**.
6. OCR RIB + validation IBAN (non persisté).
7. Récapitulatif copiable + export dossier + **impression groupée (PDF fusionné, §11)**.
8. **Système de licence en ligne** (§15) — peut être branché tôt si tu veux verrouiller dès les tests.
9. **Mise à jour des données à distance** (§16) — optionnel, peut venir après une première version stable.
10. Packaging portable Windows (`--onedir`) + dépôt GitHub.

---

## 15. Système de licence (vérification en ligne — kill switch)

Objectif : pouvoir **désactiver l'accès à distance à tout moment** (ex. impayé, fin de contrat), sans serveur à maintenir.

**Mécanisme retenu : fichier de statut hébergé sur GitHub.**
- Un fichier JSON (ex. `licences.json`) vit dans un dépôt **que toi seul contrôles**, lu par l'app via `https://raw.githubusercontent.com/<compte>/<repo>/main/licences.json`.
- Chaque client a une entrée identifiée par une **clé de licence** (chaîne opaque générée par toi, stockée dans le `config.json` du client) :
```json
{
  "MICHAEL-ORANGE-2026": { "actif": true,  "echeance": "2026-12-31", "client": "Les Menus Services Orange" }
}
```
- **Pour couper** : passer `"actif": false` (ou avancer l'échéance) et committer. L'app se bloque à la prochaine vérification.

**Comportement de l'app au démarrage :**
1. Lit sa clé dans `config.json`, appelle l'URL GitHub.
2. Si `actif:true` et `echeance` non dépassée → démarre, et **mémorise localement la date de dernière vérif réussie**.
3. Si `actif:false` ou échéance dépassée → bloque, message clair invitant à contacter le prestataire.
4. **Pas de réseau** : tolérance hors-ligne de **N jours** (param., ex. 5) depuis la dernière vérif réussie. Au-delà → blocage. Cela évite qu'une simple coupure wifi empêche de travailler, tout en gardant le kill switch efficace (la coupure prend effet en ≤ N jours).

**Garde-fous licence :**
- La clé du client est un **identifiant**, pas un secret de sécurité forte : ce système décourage l'usage non payé, il ne résiste pas à un attaquant déterminé — c'est suffisant et proportionné ici.
- Le dépôt GitHub portant `licences.json` ne doit contenir **aucune donnée bénéficiaire**, seulement des clés/statuts.
- Échec réseau ≠ crash : gérer proprement timeout et URL injoignable (→ logique de tolérance hors-ligne, pas d'erreur brute).
- Stocker la date de dernière vérif dans le dossier de l'app (fichier local simple).

> Conséquence assumée : l'app n'est donc **pas** strictement « offline ». Elle reste portable et traite les données en local, mais requiert un accès réseau au moins une fois tous les N jours.

---

## 16. Mise à jour à distance — DONNÉES uniquement (niveau 1)

**Périmètre strict pour cette version : seules les DONNÉES se mettent à jour à distance, JAMAIS le code.**

Ce qui peut se rafraîchir depuis le dépôt GitHub (lecture seule, même infra que la licence) :
- `tarifs.json` (grille tarifaire — change à chaque révision de prix)
- les modèles `.docx` (devis, conditions, mandat SEPA, CGV — si la franchise les fait évoluer)

**Mécanisme :**
- Chaque fichier de données porte un numéro de **version** (ou un hash). L'app, au démarrage (en même temps que la vérif licence), compare sa version locale à celle publiée sur GitHub.
- Si une version plus récente existe → l'app télécharge le nouveau fichier et remplace sa copie locale, en **gardant une sauvegarde** de l'ancienne (`tarifs.json.bak`) pour rollback manuel.
- Validation avant remplacement : vérifier que le fichier téléchargé est **valide** (JSON parsable / docx ouvrable) avant d'écraser. Un fichier corrompu ne doit jamais remplacer un fichier sain.

**Ce qui est INTERDIT dans cette version :**
- ❌ Télécharger et exécuter du **code** à distance (= vecteur de porte dérobée, risque de casser l'app chez le client à distance). La mise à jour du code se fait **manuellement** : nouvelle version compilée → nouveau dossier remis au client.
- ❌ Toute mise à jour automatique silencieuse du binaire.

**Évolution future (hors périmètre actuel, à ne pas coder maintenant) :**
- Niveau 2 : notifier qu'une nouvelle **version applicative** existe (« mise à jour disponible, contactez votre prestataire ») sans l'installer.
- Niveau 3 : auto-update complet du binaire — nécessiterait signature, canal sécurisé, rollback automatique, tests de pré-publication. Disproportionné tant qu'il n'y a pas un vrai parc d'agences.
