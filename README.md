# B2PC

Outil batch pour préparer et optimiser des collections de jeux rétro avec une interface PyQt6 bilingue (FR / EN).

## 🤝 Support
Discord: https://discord.gg/Vph9jwg3VV

## ✨ Fonctionnalités
- ISO / CUE → CHD (détection automatique CD / DVD)
- Extraction CHD → BIN/CUE (CD) ou ISO (DVD)
- Conversion GameCube / Wii ISO → RVZ
- Compression / Décompression wSquashFS
- Patch ISO Xbox (xISO pour xemu)
- Gestion des archives (ZIP / RAR / 7Z)
- Logs temps réel
- Mode sombre / clair
- Anglais / Français

## 🧩 Outils externes requis (dossier `ressources/`)
`chdman.exe`, `dolphin-tool.exe`, `gensquashfs.exe`, `unsquashfs.exe`, `xiso.exe`, `7za.exe`.

## 🚀 Télécharger la derniere version pour Windows
https://github.com/RetroGameSets/B2PC/releases/latest


## 🖥️ Utilisation
1. Choisir dossier source (fichiers ou archives)
2. Choisir dossier destination
3. Cliquer une opération (ex: ISO/CUE > CHD, Extraire CHD, RVZ...)
4. Suivre la progression et logs

##  Logs
Les journaux sont stockés dans `LOG/` (un fichier par opération). Export possible depuis la fenêtre de logs.

## 🌐 Langue
Commutateur FR / EN dans le footer. Les boutons et logs sont retraduits dynamiquement.


 
## 📋 Changelog

### v3.6.0.5
- Détection automatique CD/DVD lors de l'extraction CHD → utilise `chdman info` puis `extractcd` ou `extractdvd`.
- Bouton renommé : "Extraire CHD" (FR) / "Extract CHD" (EN).
- Traductions FR/EN étendues (boutons logs, fragments d’erreurs, types CHD).

### v3.6.0.4
- Info CHD : affichage rapide sans lancer de conversion lorsqu’aucun fichier n’est présent.
- Fenêtre de logs traduisible dynamiquement (boutons Stop / Save / Close / Open folder).

### v3.6.0.3
- Politique non récursive : traitement uniquement des fichiers au niveau racine + archives.
- Ajustements SquashFS (détection et extraction non récursive).

### v3.6.0.2
- Stabilisation exécution `gensquashfs` / `unsquashfs` (DLL côté ressources, ordre arguments, `--force`).
- Amélioration logs (nom fichier sécurisé, nettoyage emojis pour fichier).

### v3.6.0.1
- Amélioration arrêt conversions : suivi du process courant + terminaison propre.
- Ajout traduction dynamique fragments de logs.

### Versions antérieures (2.x - 3.5)
- Progression temps réel via parsing stdout.
- Extract-on-the-fly des archives (économie espace disque).
- Mode sombre / clair.
- Patch ISO Xbox + nettoyage des temporaires.

---
Pour l’historique complet : voir les tags Git ou anciens commits.
