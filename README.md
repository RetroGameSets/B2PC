# B2PC - Prototype Python

##SUPPORT / HELP : https://discord.gg/Vph9jwg3VV 

## Vue d'ensemble
Prototype Python pour l'application B2PC (Backup to PC) avec interface PyQt6 et handlers de conversion complets.

## 🚀 Fonctionnalités Principales

### Conversions Supportées
- **CHD v5** : Conversion ISO → CHD avec `chdman.exe`
- **RVZ** : Compression Wii/GameCube ISO → RVZ avec `dolphin-tool.exe`  
- **SquashFS** : Compression dossiers → SquashFS avec `gensquashfs.exe`
- **Xbox ISO** : Patch et conversion Xbox ISO avec `xiso.exe`

### Améliorations Récentes ✨
- ✅ **Progression temps réel** : Affichage du pourcentage d'avancement pendant les conversions
- ✅ **Extract-on-the-fly** : Extraction intelligente archive par archive (économie d'espace)
- ✅ **Mécanisme d'arrêt** : Possibilité d'interrompre les conversions en cours
- ✅ **Nettoyage automatique** : Suppression des fichiers temporaires Xbox
- ✅ **Gestion dossiers** : Correction SquashFS pour dossiers avec noms d'extension (ex: "Game.pc")

## 📁 Structure du Projet

```
python_prototype/
├── main.py              # Interface PyQt6 principale
├── handlers/            # Package des handlers de conversion
│   ├── base.py          # Base ConversionHandler (outils, logs, progrès)
│   ├── chdv5.py         # CHD v5
│   ├── rvz.py           # RVZ
│   ├── squashfs.py      # wSquashFS (compress/extract)
│   └── xbox_patch.py    # Patch Xbox ISO
├── requirements.txt     # Dépendances Python
├── README.md            # Cette documentation
└── LOG/                 # Journaux de conversion
```

## 🛠️ Installation

### Prérequis
- Python 3.8+
- Outils externes (dans `../ressources/`) :
  - `chdman.exe` (MAME CHD Manager)
  - `dolphin-tool.exe` (Dolphin Emulator) 
  - `gensquashfs.exe` / `unsquashfs.exe` (SquashFS)
  - `xiso.exe` (Xbox ISO)
  - `7za.exe` (7-Zip)

### Installation des dépendances
```bash
cd python_prototype
pip install -r requirements.txt
```

## 🎮 Utilisation

### Lancement de l'interface
```bash
python main.py
```

### Interface PyQt6
- **Sélection source** : Dossier contenant les fichiers à convertir
- **Sélection destination** : Dossier de sortie des conversions
- **Choix du type** : CHD v5, RVZ, SquashFS, ou Xbox ISO
- **Progression** : Barre de progression temps réel + logs détaillés
- **Contrôles** : Boutons Start/Stop pour gérer les conversions

### Extract-on-the-Fly
Le système extrait et traite les archives une par une :
```
Archive1.7z → Extraction → Conversion → Nettoyage
Archive2.rar → Extraction → Conversion → Nettoyage
...
```
**Avantages** : Économie d'espace disque, progression granulaire

## 🔧 Architecture Technique

### Handlers de Conversion
Chaque handler hérite de `ConversionHandler` et implémente :
- `compress()` : Logique de conversion principale
- `extract()` : Logique d'extraction (si applicable)
- `get_all_source_files()` : Détection des fichiers sources
- `check_should_stop()` : Gestion de l'arrêt utilisateur

### Progression Temps Réel
Parsing intelligent de la sortie des outils avec regex :
```python
# Exemple pour chdman.exe
progress_pattern = r"(\d+)%"
if match := re.search(progress_pattern, line):
    percentage = int(match.group(1))
    self.progress(percentage, f"Conversion en cours...")
```

### Gestion des Erreurs
- Validation des outils externes au démarrage
- Logs détaillés avec timestamps
- Nettoyage automatique en cas d'erreur
- Interface utilisateur non-bloquante

## 🧪 Tests

Des tests automatisés pourront être ajoutés ultérieurement.

## 📋 Journal des Modifications

### v2.4 - Correction Handlers SquashFS (Actuel)
- ✅ **Compression** : Syntaxe `--pack-dir` alignée sur JavaScript (résout erreur code:1)
- ✅ **Extraction** : Syntaxe `--unpack-path / --unpack-root` corrigée
- ✅ **Extensions** : Uniformisation .wsquashfs (au lieu de .squashfs)
- ✅ **Types** : Gestion harmonisée Path/string dans les deux handlers

### v2.3 - Correction SquashFS Dossiers
- ✅ Correction détection dossiers avec noms d'extension (ex: "Hotshot Racing.pc")
- ✅ Simplification logique SquashFS (focus dossiers uniquement)

### v2.2 - Nettoyage Xbox
- ✅ Suppression automatique fichiers temporaires Xbox
- ✅ Méthode `_cleanup_xbox_temp_files()`

### v2.1 - Mécanisme d'Arrêt
- ✅ Bouton Stop dans l'interface
- ✅ Variable `should_stop` pour chaque handler
- ✅ Arrêt propre des processus externes

### v2.0 - Extract-on-the-Fly
- ✅ Architecture extract-on-the-fly complète
- ✅ Économie d'espace disque significative
- ✅ Progression granulaire par archive

### v1.1 - Progression Temps Réel
- ✅ Parsing regex de la sortie des outils
- ✅ Mise à jour barre de progression en direct
- ✅ Affichage status détaillé

### v1.0 - Version Initiale
- ✅ Interface PyQt6 de base
- ✅ 4 handlers de conversion
- ✅ Import/export de configuration

## 🐛 Problèmes Connus

### Résolus ✅
- ~~Import handlers non reconnu~~ → Réparé
- ~~Progression uniquement dans logs~~ → Temps réel implémenté  
- ~~Extraction bulk inefficace~~ → Extract-on-the-fly développé
- ~~Impossible d'arrêter conversions~~ → Mécanisme d'arrêt ajouté
- ~~Erreur SquashFS code:1~~ → **Syntaxe compression/extraction corrigée**

### En cours d'investigation 🔍
- Aucun problème majeur identifié

## 🤝 Contribution

### Structure de développement
- `handlers.py` : Logique métier des conversions
- `main.py` : Interface utilisateur PyQt6  
- `test_*.py` : Tests unitaires et de régression

### Ajout d'un nouveau handler
1. Hériter de `ConversionHandler`
2. Implémenter `compress()` et/ou `extract()`
3. Ajouter à l'interface dans `main.py`
4. Créer tests de validation

## 📞 Support

### Logs de débogage
Les logs détaillés sont disponibles dans :
- `LOG/B2PC_*_YYYYMMDD_HHMMSS.log`
- Affichage temps réel dans l'interface

### Diagnostic des problèmes
1. Vérifier présence des outils externes
2. Consulter les logs de conversion
3. Tester avec les suites de tests
4. Valider les permissions de fichiers

---

**Statut** : ✅ Prototype complet et opérationnel  
**Version** : 2.4 (Handlers SquashFS corrigés)  
**Dernière mise à jour** : 2024

✅ **Threading asynchrone**
- WorkerThread pour éviter le freeze de l'UI
- Gestion des signaux PyQt6

## Structure du code

- `main.py` : Application principale
- `LogHandler` : Gestionnaire de logs personnalisé
- `WorkerThread` : Thread pour opérations longues
- `LogDialog` : Dialog modal pour logs
- `B2PCMainWindow` : Fenêtre principale

## Différences avec l'original

### Avantages
- **Performance** : Démarrage plus rapide
- **Mémoire** : Consommation réduite
- **Native** : Interface système native
- **Maintenance** : Code Python plus simple

### Équivalences parfaites
- Interface graphique identique
- Même workflow utilisateur
- Mêmes fonctionnalités
- Logs temps réel
- Mode sombre/clair

## Prochaines étapes

1. **Handlers réels** : Conversion des handlers JavaScript
2. **Outils externes** : Intégration chdman, 7za, etc.
3. **Auto-updater** : Système de mise à jour
4. **Packaging** : Création d'un exécutable
5. **Tests** : Suite de tests complète

## Exécution

```bash
cd python_prototype
python main.py
```

Le prototype exécute des conversions réelles avec barres de progression et logs détaillés.
