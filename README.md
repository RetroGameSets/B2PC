# B2PC

<p align="center">
	<img src="https://github.com/RetroGameSets/B2PC/blob/main/ressources/images/Home_screen.png" alt="Home Screen 1" width="800" />
	<br/>
	<img src="https://github.com/RetroGameSets/B2PC/blob/main/ressources/images/Home_screen_2.png" alt="Home Screen 2" width="800" />
</p>

Batch tool to prepare and optimize retro game collections with a bilingual PyQt6 interface (FR / EN).

## 🤝 Support
Discord: https://discord.gg/chz59Z9Bhj

## ✨ Features
- ISO / CUE → CHD (auto CD / DVD detection)
- CHD extraction → BIN/CUE (CD) or ISO (DVD)
- GameCube / Wii ISO → RVZ conversion
- WBFS ↔ ISO conversion (both directions)
- wSquashFS compression / extraction for Windows (.pc) and PS3 (.ps3)
- Xbox ISO patch (xISO for xemu)
- PS3 ISO decryption + extraction to .ps3 folder
- Archive handling (ZIP / RAR / 7Z)
- Real-time logs
- Dark / light mode
- English / French UI

## 🧩 Required external tools (`ressources/` folder)
`chdman.exe`, `dolphin-tool.exe`, `gensquashfs.exe`, `unsquashfs.exe`, `xiso.exe`, `wbfs_file.exe`, `ps3dec_win.exe`.

## 🚀 Download latest Windows build
https://github.com/RetroGameSets/B2PC/releases/latest

## 🖥️ Usage
1. Select source folder (files or archives)
2. Select destination folder
3. Click an operation (e.g. ISO/CUE/GDI > CHD, Extract CHD, RVZ...)
4. Follow progress & logs

## Logs
Logs are stored in `LOG/` (one file per operation). Export available from the log window.

## Language
FR / EN switch in footer. Buttons and log fragments are retranslated live.

## 📋 Changelog
https://github.com/RetroGameSets/B2PC/releases