# B2PC

<p align="center">
	<img src="https://github.com/RetroGameSets/B2PC/blob/main/ressources/images/Home_screen.png" alt="Home Screen 1" width="800" />
	<br/>
	<img src="https://github.com/RetroGameSets/B2PC/blob/main/ressources/images/Home_screen_2.png" alt="Home Screen 2" width="800" />
</p>

Batch tool to prepare and optimize retro game collections with a bilingual PyQt6 interface (FR / EN).

## 🤝 Support
Discord: https://discord.gg/Vph9jwg3VV

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

### v3.6.0.5
- Automatic CD/DVD detection for CHD extraction → uses `chdman info` then `extractcd` or `extractdvd`.
- Button renamed: "Extraire CHD" (FR) / "Extract CHD" (EN).
- Extended FR/EN translations (log buttons, error fragments, CHD types).

### v3.6.0.4
- CHD Info: fast display without starting conversion when no file present.
- Log dialog dynamically translatable (Stop / Save / Close / Open folder buttons).

### v3.6.0.3
- Non‑recursive policy: only root-level files + archives processed.
- SquashFS adjustments (non‑recursive detection & extraction).

### v3.6.0.2
- Stabilized `gensquashfs` / `unsquashfs` execution (DLL context, arg order, `--force`).
- Log improvements (sanitized filenames, emoji cleanup for file output).

### v3.6.0.1
- Improved stop logic: track running process + clean termination.
- Added dynamic translation of log fragments.

### Previous versions (2.x - 3.5)
- Real‑time progress via stdout parsing.
- Archive extract‑on‑the‑fly (disk space savings).
- Dark / light mode.
- Xbox ISO patch + temp cleanup.

---
For full history: see Git tags or earlier commits.
