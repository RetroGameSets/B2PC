# B2PC

<p align="center">
	<img src="https://github.com/RetroGameSets/B2PC/blob/main/ressources/images/Home_screen.png" alt="Home Screen 1" width="800" />
	<br/>
	<img src="https://github.com/RetroGameSets/B2PC/blob/main/ressources/images/Home_screen_2.png" alt="Home Screen 2" width="800" />
</p>

Outil batch pour préparer et optimiser des collections de jeux rétro avec une interface PyQt6 bilingue (FR / EN).

## 🤝 Support
Discord: https://discord.gg/chz59Z9Bhj

## ✨ Fonctionnalités
- ISO / CUE → CHD (détection automatique CD / DVD)
- Extraction CHD → BIN/CUE (CD) ou ISO (DVD)
- Conversion GameCube / Wii ISO → RVZ
- Conversion WBFS ↔ ISO (dans les 2 sens)
- Compression / wSquashFS Extraction pour Windows (.pc) et PS3 (.ps3)
- Patch ISO Xbox (xISO pour xemu)
- Décryptage ISO PS3 + extraction en dossier .ps3
- Gestion des archives (ZIP / RAR / 7Z)
- Logs temps réel
- Mode sombre / clair
- Anglais / Français

## 🧩 Outils externes requis (dossier `ressources/`)
`chdman.exe`, `dolphin-tool.exe`, `gensquashfs.exe`, `unsquashfs.exe`, `xiso.exe`, `wbfs_file.exe`, `ps3dec_win.exe`.

## 🚀 Télécharger la derniere version pour Windows
https://github.com/RetroGameSets/B2PC/releases/latest

## 🖥️ Utilisation
1. Choisir dossier source (fichiers ou archives)
2. Choisir dossier destination
3. Cliquer une opération (ex: ISO/CUE/GDI > CHD, Extraire CHD, RVZ...)
4. Suivre la progression et logs

##  Logs
Les journaux sont stockés dans `LOG/` (un fichier par opération). Export possible depuis la fenêtre de logs.

## 🌐 Langue
Commutateur FR / EN dans le footer. Les boutons et logs sont retraduits dynamiquement.

## 📋 Changelog
https://github.com/RetroGameSets/B2PC/releases
