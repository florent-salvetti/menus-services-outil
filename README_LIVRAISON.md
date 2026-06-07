# Installation sur le poste de l'agence — checklist

Procédure pour installer le **Générateur de documents Les Menus Services** sur le
PC de l'utilisateur (Michaël, agence d'Orange). Outil **portable** : on copie un
dossier, on configure, ça marche. Aucune installation de Python.

---

## 0. Prérequis sur le PC

| Prérequis | Pour quoi | Obligatoire ? |
|---|---|---|
| Windows 10/11 | l'app | oui |
| **Microsoft Word** (2007+) | conversion PDF pour l'impression groupée | recommandé (sinon repli LibreOffice, ou impression des `.docx` à la main) |
| Accès Internet | vérification de licence au démarrage | oui (au moins 1 fois tous les N jours, défaut 5) |
| Imprimante par défaut configurée | bouton « Imprimer le dossier complet » | optionnel |

> Pas besoin de Python, ni d'Office pour la génération des `.docx` (seulement
> pour la conversion PDF). L'OCR (Tesseract) est embarqué.

---

## 1. Copier le dossier

Copier le dossier **`MenusServices/`** complet sur le PC (ex. `C:\MenusServices\`
ou sur le Bureau). Il contient :

```
MenusServices.exe        ← l'application
_internal/               ← moteur (NE PAS modifier ni supprimer)
modeles/                 ← trames Word + grille source (remplaçables)
tarifs.json              ← grille tarifaire (modifiable à la main, voir §6)
config.example.json      ← modèle de configuration
tesseract/               ← OCR embarqué (voir §2 si absent)
```
`dossiers/` et `donnees/` se créent tout seuls au 1er lancement.

---

## 2. Vérifier / déposer Tesseract (OCR du RIB)

Si le dossier **`tesseract/`** est **déjà présent** à côté de l'exe → rien à faire.

Sinon, le déposer :
1. Installer Tesseract (UB Mannheim) sur une machine : <https://github.com/UB-Mannheim/tesseract/wiki> → `tesseract-ocr-w64-setup-5.x.x.exe`, en cochant **French (fra)**.
2. Copier le contenu de l'installation dans `MenusServices/tesseract/` de sorte à obtenir :
   ```
   MenusServices/tesseract/tesseract.exe
   MenusServices/tesseract/tessdata/fra.traineddata
   MenusServices/tesseract/tessdata/eng.traineddata
   ```
> L'OCR n'est qu'une aide : l'IBAN reste **toujours validé à l'écran** (mod 97).
> Sans Tesseract, la saisie manuelle de l'IBAN fonctionne normalement.

---

## 3. Créer `config.json` (clé de licence + agence)

1. **Copier** `config.example.json` → **`config.json`** (dans le même dossier).
2. Éditer `config.json` :
   - `licence.cle` : la **clé du client** (ex. `MICHAEL-ORANGE-2026`).
   - `licence.url_statut` : l'URL **raw GitHub** du fichier de statut, ex.
     `https://raw.githubusercontent.com/<compte>/<repo-licences>/main/licences.json`
   - `licence.tolerance_hors_ligne_jours` : nb de jours de tolérance sans réseau (défaut 5).
   - `libreoffice.soffice` : laisser **vide** si Word est présent (Word est utilisé
     en priorité) ou si LibreOffice est embarqué dans `libreoffice/`. Sinon, chemin
     vers un `soffice.exe`.

> ⚠️ `config.json` n'est **jamais** versionné (il contient la clé). Éditer en
> UTF-8 ; un éventuel BOM ajouté par Notepad est toléré.

---

## 4. Activer la licence (côté prestataire)

Dans le dépôt **privé** de licences (séparé, contrôlé par le prestataire), le
fichier `licences.json` doit contenir l'entrée de la clé :
```json
{
  "MICHAEL-ORANGE-2026": { "actif": true, "echeance": "2026-12-31", "client": "Les Menus Services Orange" }
}
```
- **Couper l'accès** plus tard : passer `"actif": false` (ou avancer `echeance`)
  et committer → blocage au prochain démarrage du client (délai ≤ cache GitHub, ~5 min).
- Ce dépôt ne contient **aucune donnée bénéficiaire**, uniquement des clés/statuts.

---

## 5. Lancer et vérifier

1. **Lancer** : double-clic sur `MenusServices.exe`.
   - Licence OK → la fenêtre s'ouvre.
   - Licence KO → message clair (clé + « contactez votre prestataire »), l'app ne démarre pas.
2. **Vérification technique** (checklist d'installation), en ligne de commande
   dans le dossier de l'exe :
   ```
   MenusServices.exe --selftest
   ```
   Doit afficher **`SELFTEST PASS`** et confirmer :
   - `RACINE` = le dossier de l'exe ;
   - licence lue (`autorise=True`) ;
   - génération `devis=True conditions=True mandat=True cgv=True` ;
   - `Tesseract présent=True` et OCR `valide=True` (si `tesseract/` déposé).

---

## 6. Usage courant

- **Saisie** : remplir le formulaire (client, bénéficiaire, formules, tournée
  T1/T2, jours, banque). L'IBAN peut être pré-rempli depuis un RIB (bouton
  « 📷 Lire un RIB ») — **toujours vérifier** le ✓ vert avant génération.
- **Générer** : produit un dossier `dossiers/NOM_Prénom_AAAA-MM-JJ/` avec devis,
  conditions, mandat SEPA (si IBAN valide) et CGV.
- **Récap** : bouton « 📋 Copier » → coller dans le CRM (l'outil ne touche jamais au CRM).
- **Imprimer** : bouton « 🖨 Imprimer le dossier complet » → PDF fusionné (via Word)
  rangé dans le dossier + envoi imprimante. En cas d'échec, les `.docx` restent disponibles.

---

## 7. Mises à jour (manuelles)

- **Tarifs** : remplacer `tarifs.json` à côté de l'exe (par la nouvelle grille).
  Rien d'autre à faire, rechargé au prochain lancement.
- **Trames Word** : remplacer les fichiers dans `modeles/` (garder les mêmes noms).
- **Application** : nouvelle version = nouveau dossier `MenusServices/` remis par
  le prestataire (recopier par-dessus en conservant `config.json`, `tarifs.json`
  personnalisé, `dossiers/`, `donnees/`).

---

## 8. Données & RGPD (rappel)

- Traitement **local** ; seul appel réseau : la vérification de licence.
- **IBAN/BIC non conservés** par l'outil (servent à générer le mandat, puis écartés) ;
  le RIB importé n'est **ni copié ni supprimé**.
- La base locale (dossiers bénéficiaires) **n'est pas chiffrée** dans cette version
  (risque assumé) : protéger l'accès au PC. Un contrat de sous-traitance RGPD doit
  être signé en parallèle (hors logiciel).
