![Logo B2PC](ressources/images/logo.png)
# Batch Games Converter (B2PC)

![Screenshot](https://github.com/RetroGameSets/B2PC/blob/main/B2PC%20Home%20screen.png)
![Screenshot](https://github.com/RetroGameSets/B2PC/blob/main/B2PC%20Log%20screen.png)

**Batch Games Converter (B2PC)** est une application de bureau conçue pour simplifier la conversion, l'extraction et le traitement des ROMs de jeux rétro pour divers systèmes, notamment PS1, PS2, Dreamcast, PCEngineCD, SegaCD, Saturn, Xbox, GameCube et Wii. Développée par RetroGameSets.fr, B2PC vise à offrir une interface utilisateur intuitive pour automatiser des tâches comme la conversion de formats de fichiers, l'extraction de contenus, et le patchage pour la compatibilité avec des émulateurs modernes.

> **Note** : B2PC est en cours de développement actif. Certaines fonctionnalités sont actuellement disponibles, avec de nouvelles améliorations prévues à l'avenir. Dernière mise à jour : 25 mai 2025.

## Fonctionnalités actives

### 1. Conversion CUE/GDI/ISO en CHD v5
- **Description** : Convertit les fichiers `.iso`, `.cue`, et `.gdi` (avec leurs fichiers `.bin` associés) en format `.chd` (version 5) pour une meilleure compatibilité avec les émulateurs comme RetroArch.
- **Détails** :
  - Gère les fichiers directement dans le dossier source ou dans des archives (`.zip`, `.7z`, `.gz`, `.rar`).
  - Extrait les archives dans le dossier source, convertit les fichiers en `.chd`, et place les résultats dans un sous-dossier `CHD` du dossier destination.
  - Supprime automatiquement les fichiers extraits après conversion pour éviter l’encombrement.
  - Fournit des logs détaillés (ex. « Compression complete ... final ratio = 65.6% ») et une barre de progression pour suivre l’avancement.
  - Affiche les erreurs critiques et un résumé final (jeux convertis, ignorés, erreurs).
- **Utilisation** : Sélectionnez un dossier source contenant des fichiers ou archives, un dossier destination, et cliquez sur **CUE/GDI/ISO to CHD v5** dans l’onglet **Conversion**.

### 2. Extraction CHD
- **Description** : Extrait les fichiers `.chd` pour restaurer leurs contenus originaux (`.iso`, `.cue`, ou `.gdi` avec `.bin`) afin de permettre des modifications ou une vérification.
- **Détails** :
  - Traite les fichiers `.chd` directement dans le dossier source ou extraits depuis des archives (`.zip`, `.7z`, `.gz`, `.rar`).
  - Extrait les contenus dans le dossier source et place les fichiers restaurés dans un sous-dossier `Extracted` du dossier destination.
  - Supprime automatiquement les fichiers temporaires après extraction.
  - Fournit des logs détaillés et une barre de progression pour suivre l’opération.
  - Gère les erreurs (ex. fichiers CHD invalides) avec des notifications claires.
- **Utilisation** : Sélectionnez un dossier source contenant des fichiers `.chd` ou des archives, un dossier destination, et cliquez sur **Extract CHD** dans l’onglet **Conversion**.

### 3. Merge bin /cue
- **Description** : Fusion des jeux au format .cue avec multiples fichiers .bin pour ceux qui souhaitent conserver ce format de fichier, mais pas un grand nombre de fichiers .bin (track01, track02, ...)
- **Détails** :
  - Traite les fichiers `.cue` et leurs `.bin` associés directement dans le dossier source ou extraits depuis des archives (`.zip`, `.7z`, `.gz`, `.rar`).
  - Extrait les contenus dans le dossier source et converti en CHD les fichiers temporaires dans un sous-dossier `CHD_TEMP` du dossier destination, puis extrait le CHD en un seul BIN/CUE dans le dossier Merged_CUE.
  - Supprime automatiquement les fichiers temporaires CHD après conversion.
  - Fournit des logs détaillés et une barre de progression pour suivre l’opération.
  - Gère les erreurs (ex. fichiers avec un seul BIN, ou BIN manquant dans la liste du CUE) avec des notifications claires.
- **Utilisation** : Sélectionnez un dossier source contenant des fichiers `.cue` et `.bin` ou des archives, un dossier destination, et cliquez sur **Merge BIN/CUE** dans l’onglet **Conversion**.

### 4. Patch XBOX ISO pour xemu
- **Description** : Patche les fichiers ISO Xbox Classic pour les rendre compatibles avec l’émulateur xemu.
- **Détails** :
  - Traite les fichiers `.iso` directement dans le dossier source ou extraits depuis des archives (`.zip`, `.7z`, `.gz`, `.rar`).
  - Extrait les archives dans le dossier source, patche les ISO avec `xiso.exe`, et place les résultats dans un sous-dossier `xbox` du dossier destination.
  - Supprime les fichiers extraits après conversion.
  - Fournit des logs détaillés et une barre de progression.
  - Affiche un résumé des jeux patchés, ignorés, et des erreurs rencontrées.
- **Utilisation** : Sélectionnez un dossier source avec des ISO ou archives Xbox, un dossier destination, et cliquez sur **Patch XBOX ISO xemu** dans l’onglet **Patch**.

### 5. Conversion / Compression Gamecube ISO en RVZ pour Dolphin
- **Description** : Convertit et compresse les fichiers ISO Gamecube/Wii en format `.rvz` pour un gain de place et une meilleure compatibilité avec l’émulateur Dolphin.
- **Détails** :
  - Traite les fichiers `.iso` directement dans le dossier source ou extraits depuis des archives (`.zip`, `.7z`, `.gz`, `.rar`).
  - Extrait les archives dans le dossier source, convertit les ISO en `.rvz` avec `DolphinTool.exe`, et place les résultats dans un sous-dossier `RVZ` du dossier destination.
  - Supprime les fichiers extraits après conversion.
  - Fournit des logs détaillés (ex. « Compressing, 50.0% complete ») et une double barre de progression (totale et fichier en cours).
  - Vérifie la compatibilité des ISO avant conversion et gère les erreurs (ex. fichiers incompatibles).
- **Utilisation** : Sélectionnez un dossier source avec des ISO ou archives Gamecube/Wii, un dossier destination, et cliquez sur **Convert ISO to RVZ** dans l’onglet **Conversion**.

## Prérequis

- **Système d’exploitation** : Windows (testé sur Windows 10/11).
- **Outils inclus** :
  - `7za.exe` (gestion des archives).
  - `chdman.exe` (conversion et extraction en CHD).
  - `xiso.exe` (patchage Xbox).
  - `DolphinTool.exe` (conversion en RVZ).
- **Espace disque** : Prévoir de l’espace pour les fichiers extraits, convertis, et restaurés.

## Télécharger B2PC
Téléchargez la dernière version bêta pour Windows depuis [GitHub Releases](https://github.com/RetroGameSets/B2PC/releases).

## Contributions et support
- **Signaler des bugs** : Ouvrez une issue sur [GitHub](https://github.com/RetroGameSets/B2PC/issues).
- **Contribuer** : Forkez le dépôt, proposez des pull requests, et consultez les guidelines de contribution.
- **Contact** : Visitez [RetroGameSets.fr](https://retrogamesets.fr) pour plus d’informations ou du support.

## Licence
Ce projet est sous licence [MIT](LICENSE), sauf indication contraire.