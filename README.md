![Logo B2PC](ressources/images/logo.png)
# Batch Games Converter (B2PC)

**Batch Games Converter (B2PC)** est une application de bureau conçue pour simplifier la conversion et le traitement des ROMs de jeux rétro pour divers systèmes, notamment PS1, PS2, Dreamcast, PCEngineCD, SegaCD, Saturn, Xbox, et Wii. Développée par RetroGameSets.fr, B2PC vise à offrir une interface utilisateur intuitive pour automatiser des tâches comme la conversion de formats de fichiers et le patchage pour la compatibilité avec des émulateurs modernes.

> **Note** : B2PC est en cours de développement actif. Seules certaines fonctionnalités sont actuellement disponibles, mais d'autres seront ajoutées à l'avenir.

## Fonctionnalités actives

### 1. Conversion CUE/GDI/ISO en CHD v5
- **Description** : Convertit les fichiers `.iso`, `.cue`, et `.gdi` (avec leurs fichiers `.bin` associés) en format `.chd` (version 5) pour une meilleure compatibilité avec les émulateurs comme RetroArch.
- **Détails** :
  - Gère les fichiers directement dans le dossier source ou dans des archives (`.zip`, `.7z`, `.gz`, `.rar`).
  - Extrait les archives dans le dossier source, convertit les fichiers en `.chd`, et place les résultats dans un sous-dossier `CHD` du dossier destination.
  - Supprime automatiquement les fichiers extraits après conversion pour éviter l’encombrement.
  - Affiche uniquement les erreurs critiques et le résumé final de la conversion dans les logs (ex. « Compression complete ... final ratio = 65.6% »).
- **Utilisation** : Sélectionnez un dossier source contenant des fichiers ou archives, un dossier destination, et cliquez sur **CUE/GDI/ISO to CHD v5** dans l’onglet **Conversion**.

### 2. Patch XBOX ISO pour xemu
- **Description** : Patche les fichiers ISO Xbox Classic pour les rendre compatibles avec l’émulateur xemu.
- **Détails** :
  - Traite les fichiers `.iso` directement dans le dossier source ou extraits depuis des archives (`.zip`, `.7z`, `.gz`, `.rar`).
  - Extrait les archives dans le dossier source, patche les ISO avec `xiso.exe`, et place les résultats dans un sous-dossier `xbox` du dossier destination.
  - Supprime les fichiers extraits après conversion.
  - Fournit des logs détaillés et une barre de progression.
- **Utilisation** : Sélectionnez un dossier source avec des ISO ou archives Xbox, un dossier destination, et cliquez sur **Patch XBOX ISO xemu** dans l’onglet **Patch**.

## Prérequis

- **Système d’exploitation** : Windows (testé sur Windows 10/11).
- **Node.js** : Version 16 ou supérieure.
- **Dépendances** :
  - `electron` pour l’interface de bureau.
  - `node-7z` pour la gestion des archives.
  - `tailwindcss` pour les styles.
- **Outils inclus** :
  - `7za.exe` (gestion des archives).
  - `chdman.exe` (conversion en CHD).
  - `xiso.exe` (patchage Xbox).
- **Espace disque** : Prévoir de l’espace pour les fichiers extraits et convertis.

## Télécharger B2PC
Téléchargez la version bêta 3.0.0-beta.1 pour Windows (installateur NSIS), macOS, ou Linux depuis [GitHub Releases](https://github.com/RetroGameSets/B2PC/releases).