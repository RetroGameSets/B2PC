APP_VERSION = "3.6.0.3"
UPDATE_URL = "https://raw.githubusercontent.com/RetroGameSets/B2PC/refs/heads/main/ressources/last_version.json"  # À adapter selon votre repo

import os
import sys
import urllib.request
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QLabel, QPushButton, QLineEdit, QTextEdit, QProgressBar,
    QFileDialog, QDialog, QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QCursor
from typing import Optional
import logging
from datetime import datetime
import subprocess
from handlers.chdv5 import ChdV5Handler
from handlers.rvz import RvzHandler
from handlers.squashfs import SquashFSHandler
from handlers.xbox_patch import XboxPatchHandler
from handlers.extract_chd import ExtractChdHandler
from handlers.merge_bin_cue import MergeBinCueHandler
from handlers.base import ConversionHandler
import json
import re

# Fonction utilitaire pour compatibilité PyInstaller
def resource_path(relative_path):
    """Retourne le chemin absolu vers une ressource, compatible PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path) # type: ignore
    return os.path.join(os.path.abspath("."), relative_path)

def check_for_update():
    try:
        with urllib.request.urlopen(UPDATE_URL, timeout=5) as response:
            data = response.read().decode("utf-8")
            import json
            info = json.loads(data)
            latest_version = info.get("version", "")
            download_url = info.get("url", "")
            if latest_version and latest_version != APP_VERSION:
                import ctypes
                msg = f"Une nouvelle version ({latest_version}) est disponible !\nTélécharger ?"
                if ctypes.windll.user32.MessageBoxW(0, msg, "Mise à jour disponible", 1) == 1:
                    import webbrowser
                    webbrowser.open(download_url)
                    sys.exit(0)  # Ferme l'application immédiatement
    except Exception as e:
        print(f"[Update] Impossible de vérifier la mise à jour : {e}")

# Appeler le check au démarrage
check_for_update()

class LogHandler(logging.Handler):
    """Handler personnalisé pour rediriger les logs vers l'interface"""
    def __init__(self, signal):
        super().__init__()
        self.signal = signal

    def emit(self, record):
        msg = self.format(record)
        self.signal.emit(msg)

class WorkerThread(QThread):
    """Thread worker pour les opérations de conversion avec logs réels"""
    progress_update = pyqtSignal(int, str)
    log_message = pyqtSignal(str)
    finished = pyqtSignal(dict)

    def __init__(self, operation, source_folder, dest_folder):
        super().__init__()
        self.operation = operation
        self.source_folder = source_folder
        self.dest_folder = dest_folder
        self.log_file = None
        self.handler: Optional[ConversionHandler] = None  # Référence au handler pour pouvoir l'arrêter
        self.setup_logging()
    
    def stop_conversion(self):
        """Arrête la conversion en cours"""
        if self.handler:
            self.handler.stop_conversion()
            self.log_both("🛑 Demande d'arrêt envoyée au handler")

    def setup_logging(self):
        """Configure le système de logging avec fichier"""
        # Créer le dossier LOG
        log_dir = Path("LOG")
        log_dir.mkdir(exist_ok=True)
        
        # Nom du fichier log avec timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        operation_name = self.operation.replace("/", "_").replace(" ", "_")
        log_filename = f"B2PC_{operation_name}_{timestamp}.log"
        self.log_file = log_dir / log_filename
        
        # Configurer le logger
        self.logger = logging.getLogger(f"B2PC_{operation_name}")
        self.logger.setLevel(logging.INFO)
        
        # Handler pour fichier
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # Format des logs
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        # Ajouter le handler
        self.logger.addHandler(file_handler)
        
        self.log_message.emit(f"📄 Fichier de log créé: {self.log_file.name}")

    def log_both(self, message):
        """Log vers fichier ET interface"""
        # Nettoyer le message des emojis pour le fichier
        clean_message = message.encode('ascii', 'ignore').decode('ascii')
        self.logger.info(clean_message)
        
        # Affichage interface avec emojis
        self.log_message.emit(message)

    def run(self):
        """Exécute la conversion (mode réel uniquement)"""
        try:
            self.log_both(f"🚀 Début de l'opération : {self.operation}")
            self.log_both(f"📁 Dossier source: {self.source_folder}")
            self.log_both(f"📁 Dossier destination: {self.dest_folder}")
            
            # Conversion réelle obligatoire
            self.log_both("⚡ Mode conversion réelle activé")
            results = self.run_conversion()
            
            self.log_both("=" * 50)
            self.log_both("🎉 Opération terminée avec succès!")
            self.log_both(f"📄 Log sauvegardé: {self.log_file}")
            
            self.finished.emit(results)
        except Exception as e:
            error_msg = f"❌ Erreur critique : {str(e)}"
            self.log_both(error_msg)
            self.finished.emit({'error': str(e)})

    def run_conversion(self):
        """Exécute une vraie conversion avec les handlers"""
        self.progress_update.emit(10, "Initialisation des outils")
        
        # Sélectionner le bon handler
        handler = None
        tools_path = Path("ressources")  # Chemin vers les outils
        
        def log_callback(msg):
            self.log_both(f"🔧 {msg}")
        
        def progress_callback(progress, msg):
            self.progress_update.emit(progress, msg)
        
        try:
            if self.operation == "Conversion CHD v5":
                self.handler = ChdV5Handler(str(tools_path), log_callback, progress_callback)
            elif "Extract CHD" in self.operation:
                self.handler = ExtractChdHandler(str(tools_path), log_callback, progress_callback)
            elif "Merge BIN/CUE" in self.operation:
                self.handler = MergeBinCueHandler(str(tools_path), log_callback, progress_callback)
            elif "RVZ" in self.operation:
                self.handler = RvzHandler(str(tools_path), log_callback, progress_callback)
            elif "wSquashFS" in self.operation:
                self.handler = SquashFSHandler(str(tools_path), log_callback, progress_callback)
            elif "Xbox" in self.operation:
                self.handler = XboxPatchHandler(str(tools_path), log_callback, progress_callback)
            else:
                raise ValueError(f"Handler non disponible pour: {self.operation}")

            # Configurer le handler
            self.handler.source_folder = self.source_folder
            self.handler.dest_folder = self.dest_folder

            # Valider les outils
            if not self.handler.validate_tools():
                raise Exception("Outils requis manquants")

            # Exécuter la conversion
            self.progress_update.emit(20, "Conversion en cours")

            # Pour SquashFSHandler, on peut appeler compress/extract selon l'opération
            if isinstance(self.handler, SquashFSHandler):
                if "Compression" in self.operation:
                    results = self.handler.compress()
                elif any(k in self.operation for k in ("Extraction", "Extract", "Décompression")):
                    results = self.handler.extract()
                else:
                    results = self.handler.convert()
            else:
                results = self.handler.convert()

            return results
        except Exception as e:
            self.log_both(f"❌ Erreur handler réel: {e}")
            raise

class LogDialog(QDialog):
    """Dialog modal pour afficher les logs"""
    stop_requested = pyqtSignal()  # Signal pour demander l'arrêt
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Logs de conversion")
        self.setModal(True)
        self.resize(800, 600)
        self.worker_thread = None  # Référence au thread worker
        
        layout = QVBoxLayout(self)
        
        # Zone de logs
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_text)
        
        # Barre de progression
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Boutons
        button_layout = QHBoxLayout()
        
        # Bouton d'arrêt (rouge)
        self.stop_button = QPushButton("🛑 Arrêter")
        self.stop_button.setObjectName("stopButton")
        
        self.close_button = QPushButton("Fermer")
        self.close_button.clicked.connect(self.accept)
        
        self.open_log_folder_button = QPushButton("Ouvrir dossier LOG")
        self.open_log_folder_button.clicked.connect(self.open_log_folder)
        
        self.save_log_button = QPushButton("💾 Sauvegarder logs")
        self.save_log_button.clicked.connect(self.save_current_log)
        
        button_layout.addWidget(self.stop_button)
        button_layout.addStretch()
        button_layout.addWidget(self.save_log_button)
        button_layout.addWidget(self.open_log_folder_button)
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)
        

    def set_worker_thread(self, worker_thread):
        """Définit la référence au thread worker pour pouvoir l'arrêter"""
        self.worker_thread = worker_thread
        
    def request_stop(self):
        """Demande l'arrêt de la conversion"""
        if self.worker_thread:
            self.stop_button.setEnabled(False)
            self.stop_button.setText("🛑 Arrêt en cours...")
            self.worker_thread.stop_conversion()
            self.add_log("🛑 Demande d'arrêt envoyée...")
        
    def on_finished(self, results):
        """Appelé quand la conversion est terminée"""
        self.stop_button.setEnabled(False)
        self.stop_button.setText("✅ Terminé")
        
        if results.get('stopped', False):
            self.add_log("🛑 Conversion arrêtée par l'utilisateur")
        else:
            self.add_log("✅ Conversion terminée")
    
    def add_log(self, message):
        """Ajoute un message au log avec coloration"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Traduction dynamique si interface en anglais
        parent = self.parent()
        # Vérification stricte du type pour éviter l'avertissement de l'analyseur statique
        if parent and isinstance(parent, B2PCMainWindow) and parent.language == 'en':
            # Appel direct garanti par isinstance
            message = parent.translate_log_message(message)  # type: ignore[attr-defined]
        
        # Déterminer la couleur selon le type de message
        if "❌" in message or "Erreur" in message or "Échec" in message:
            color = "#dc2626"  # Rouge
        elif "✅" in message or "Succès" in message or "terminée" in message:
            color = "#16a34a"  # Vert
        elif "⏳" in message or "🔄" in message or "Traitement" in message:
            color = "#eab308"  # Jaune
        elif "🎉" in message or "Statistiques" in message:
            color = "#8b5cf6"  # Violet
        else:
            color = "#374151"  # Gris foncé
        
        formatted_message = f'<span style="color: {color};">[{timestamp}] {message}</span><br>'
        self.log_text.insertHtml(formatted_message)
        self.log_text.ensureCursorVisible()
    
    def update_progress(self, value, text):
        """Met à jour la barre de progression"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(value)
        self.progress_bar.setFormat(text)
    
    def hide_progress(self):
        """Cache la barre de progression"""
        self.progress_bar.setVisible(False)
    
    def open_log_folder(self):
        """Ouvre le dossier des logs"""
        log_dir = Path("LOG")
        if log_dir.exists():
            if sys.platform == "win32":
                flags = subprocess.CREATE_NO_WINDOW
                subprocess.run(["explorer", str(log_dir)], creationflags=flags)

    def save_current_log(self):
        """Sauvegarde le log actuel affiché"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename, _ = QFileDialog.getSaveFileName(
            self,
            ("Sauvegarder les logs affichés" if getattr(self.parent(), 'language', 'fr') == 'fr' else "Save displayed logs"),
            f"B2PC_logs_interface_{timestamp}.txt",
            ("Fichiers texte (*.txt)" if getattr(self.parent(), 'language', 'fr') == 'fr' else "Text files (*.txt)")
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    if getattr(self.parent(), 'language', 'fr') == 'fr':
                        f.write("B2PC - Logs de conversion (Interface)\n")
                        f.write(f"Généré le: {datetime.now()}\n")
                    else:
                        f.write("B2PC - Conversion logs (Interface)\n")
                        f.write(f"Generated on: {datetime.now()}\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(self.log_text.toPlainText())
                
                # Afficher confirmation
                if getattr(self.parent(), 'language', 'fr') == 'fr':
                    self.add_log(f"💾 Logs sauvegardés: {Path(filename).name}")
                else:
                    self.add_log(f"💾 Logs saved: {Path(filename).name}")
            except Exception as e:
                if getattr(self.parent(), 'language', 'fr') == 'fr':
                    self.add_log(f"❌ Erreur sauvegarde: {str(e)}")
                else:
                    self.add_log(f"❌ Save error: {str(e)}")

class B2PCMainWindow(QMainWindow):
    """Fenêtre principale de l'application B2PC"""
    
    def __init__(self):
        super().__init__()
        self.source_folder = ""
        self.dest_folder = ""
        self.dark_mode = False
        self.current_worker = None
        self.log_dialog = None
        # Charger paramétrage (langue) avant construction UI
        self.language = 'fr'
        self._settings = {}
        self._translation_store = []  # Liste de tuples (widget, base_text_key, dynamic_callable?)

        # Dictionnaire de traductions (clé = texte FR original)
        self.translations_en = {
            'Dossier source (Archives autorisées):': 'Source folder (archives allowed):',
            'Sélectionnez un dossier source...': 'Select a source folder...',
            'Parcourir': 'Browse',
            'Dossier destination:': 'Destination folder:',
            'Sélectionnez un dossier destination...': 'Select a destination folder...',
            'Conversion': 'Conversion',
            'CHD v5': 'CHD v5',
            'CHD v5 DVD': 'CHD v5 DVD',
            'Extract CHD > BIN/CUE': 'Extract CHD > BIN/CUE',
            'Merge BIN/CUE': 'Merge BIN/CUE',
            'GC/WII ISO to RVZ': 'GC/WII ISO to RVZ',
            'WII ISO to WBFS': 'WII ISO to WBFS',
            'Compression / Décompression': 'Compression / Decompression',
            'Compression wSquashFS': 'wSquashFS Compression',
            'Décompression wSquashFS': 'wSquashFS Extraction',
            'Outils': 'Tools',
            'Patch Xbox ISO': 'Patch Xbox ISO',
            'Eteindre la lumière 🌙': 'Enable dark mode 🌙',
            'Allumer la lumière ☀️': 'Disable dark mode ☀️',
            '🛑 Arrêter': '🛑 Stop',
            '🛑 Arrêt en cours...': '🛑 Stopping...',
            'Fermer': 'Close',
            '💾 Sauvegarder logs': '💾 Save logs',
            'Ouvrir dossier LOG': 'Open LOG folder',
            'Logs de conversion': 'Conversion logs',
            'Conversion CHD v5': 'CHD v5 Conversion',
            'Conversion CHD v5 DVD': 'CHD v5 DVD Conversion',
            'Extract CHD': 'Extract CHD',
            'Merge BIN/CUE': 'Merge BIN/CUE',
            'Conversion ISO vers RVZ': 'ISO to RVZ Conversion',
            'Décompression wSquashFS': 'wSquashFS Extraction',
            'Patch Xbox ISO': 'Patch Xbox ISO',
            'Infos CHD': 'CHD Info',
            'Analyse CHD': 'CHD Analysis',
            'Taille originale': 'Original size',
            'Taille compressée': 'Compressed size',
            'Ratio': 'Ratio'
        }

        # Fragments de traduction pour les messages de log (FR -> EN)
        self.log_translations_en = {
            "Début de l'opération": "Start of operation",
            "Dossier source": "Source folder",
            "Dossier destination": "Destination folder",
            "Mode conversion réelle activé": "Real conversion mode enabled",
            "Opération terminée avec succès": "Operation completed successfully",
            "Log sauvegardé": "Log saved",
            "Erreur critique": "Critical error",
            "Demande d'arrêt envoyée": "Stop request sent",
            "Conversion arrêtée par l'utilisateur": "Conversion stopped by user",
            "Conversion terminée": "Conversion finished",
            "Fichier de log créé": "Log file created",
            "Outil manquant": "Missing tool",
            "Tous les outils sont présents": "All required tools are present",
            "Arrêt de la conversion demandé": "Conversion stop requested",
            "Processus terminé": "Process terminated",
            "Processus forcé à s'arrêter": "Process force-stopped",
            "Impossible d'arrêter le processus": "Unable to stop process",
            "Exception lors de l'exécution": "Exception while running",
            "Conversion arrêtée": "Conversion stopped",
            "Archive extraite": "Archive extracted",
            "Échec extraction": "Extraction failed",
            "Extraction archive": "Extracting archive",
            "Fichier déjà converti": "File already converted",
            "Déjà converti": "Already converted",
            "Échec conversion": "Conversion failed",
            "Extension ignorée": "Ignored extension",
            "Sources détectées": "Detected sources",
            "Fichier": "File",
            "Trouvé": "Found",
            "fichiers exploitables dans l'archive": "processable files in archive",
            "Logs sauvegardés": "Logs saved",
            "Erreur sauvegarde": "Save error",
            "Dossier temporaire créé": "Temporary folder created",
            "Dossier temporaire nettoyé": "Temporary folder cleaned",
            "Erreur nettoyage dossier temporaire": "Temp folder cleanup error"
        }

        # Charger les paramètres persistants puis configuration UI
        self._settings = self.load_settings()
        if isinstance(self._settings, dict):
            self.language = self._settings.get('language', 'fr')
        # Charger la configuration UI
        self.ui_config = self.load_ui_config()

        self.init_ui()
        self.apply_styles()
        # Appliquer la langue chargée
        if self.language == 'en':
            # Mettre à jour combo si déjà créé dans footer
            if hasattr(self, 'language_combo'):
                idx = self.language_combo.findData('en')
                if idx >= 0:
                    self.language_combo.setCurrentIndex(idx)
            self.retranslate_ui()

    # ---------------- Paramètres / Configuration ----------------
    def get_config_dir(self):
        base = os.getenv('APPDATA') or str(Path.home())
        cfg_dir = Path(base) / 'B2PC'
        cfg_dir.mkdir(parents=True, exist_ok=True)
        return cfg_dir

    def load_settings(self):
        try:
            cfg_file = self.get_config_dir() / 'settings.json'
            if cfg_file.exists():
                with open(cfg_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def save_settings(self):
        try:
            cfg_file = self.get_config_dir() / 'settings.json'
            data = {
                'language': self.language
            }
            with open(cfg_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def load_ui_config(self):
        """Charge la configuration UI depuis ui.json (chemin compatible PyInstaller)"""
        try:
            ui_json_path = resource_path("ressources/themes/ui.json")
            if not os.path.exists(ui_json_path):
                print(f"[ERREUR] Fichier ui.json introuvable : {ui_json_path}")
                return {}
            with open(ui_json_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            if "colors" not in config:
                print(f"[ERREUR] Clé 'colors' absente dans ui.json. Contenu: {config}")
            return config
        except Exception as e:
            print(f"Erreur lors du chargement de ui.json : {e}")
            return {}

    def init_ui(self):
        """Initialise l'interface utilisateur"""
        self.setWindowTitle("B2PC - Batch Retro Games Converter")

        # Charger les dimensions depuis ui.json
        window_config = self.ui_config.get("window", {})
        self.setMinimumSize(window_config.get("minWidth", 800), window_config.get("minHeight", 600))
        self.resize(window_config.get("width", 1024), window_config.get("height", 700))

        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(40, 20, 40, 20)

        # Header avec logo et description
        self.create_header(main_layout)

        # Section des dossiers
        self.create_folder_section(main_layout)

        # Section des boutons de conversion
        self.create_conversion_section(main_layout)

        # Footer
        self.create_footer(main_layout)

        # Mettre à jour l'état des boutons
        self.update_button_states()

        # Forcer l'affichage en 3 colonnes par défaut
        self.arrange_button_groups()

        # Recharger le style après toute l'UI
        self.apply_styles()
    
    def create_header(self, parent_layout):
        """Crée la section header avec logo et descriptions"""
        header_layout = QVBoxLayout()
        header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Logo (placeholder)
        logo_label = QLabel("🎮 B2PC")
        logo_label.setObjectName("logoLabel")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(logo_label)
        
        # Réduction des marges
        header_layout.setContentsMargins(0, 10, 0, 10)
        
        parent_layout.addLayout(header_layout)
    
    def create_folder_section(self, parent_layout):
        """Crée la section de sélection des dossiers (responsive)"""
        folder_container = QWidget()
        folder_layout = QVBoxLayout(folder_container)
        folder_layout.setSpacing(15)

        folders_row = QHBoxLayout()
        folders_row.setSpacing(20)

        # Source
        source_container = QWidget()
        source_layout = QVBoxLayout(source_container)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_label = QLabel("Dossier source (Archives autorisées):")
        source_label.setObjectName("sourceLabel")
        source_layout.addWidget(source_label)
        self._translation_store.append((source_label, 'Dossier source (Archives autorisées):'))
        source_row = QHBoxLayout()
        self.source_input = QLineEdit()
        self.source_input.setReadOnly(True)
        self.source_input.setPlaceholderText("Sélectionnez un dossier source...")
        self._translation_store.append((self.source_input, 'Sélectionnez un dossier source...'))
        self.source_input.textChanged.connect(self.update_button_states)
        source_row.addWidget(self.source_input)
        self.source_button = QPushButton("Parcourir")
        self.source_button.clicked.connect(self.select_source_folder)
        source_row.addWidget(self.source_button)
        self._translation_store.append((self.source_button, 'Parcourir'))
        source_layout.addLayout(source_row)
        folders_row.addWidget(source_container)

        # Destination
        dest_container = QWidget()
        dest_layout = QVBoxLayout(dest_container)
        dest_layout.setContentsMargins(0, 0, 0, 0)
        dest_label = QLabel("Dossier destination:")
        dest_label.setObjectName("destLabel")
        dest_layout.addWidget(dest_label)
        self._translation_store.append((dest_label, 'Dossier destination:'))
        dest_row = QHBoxLayout()
        self.dest_input = QLineEdit()
        self.dest_input.setReadOnly(True)
        self.dest_input.setPlaceholderText("Sélectionnez un dossier destination...")
        self._translation_store.append((self.dest_input, 'Sélectionnez un dossier destination...'))
        self.dest_input.textChanged.connect(self.update_button_states)
        dest_row.addWidget(self.dest_input)
        self.dest_button = QPushButton("Parcourir")
        self.dest_button.clicked.connect(self.select_dest_folder)
        dest_row.addWidget(self.dest_button)
        self._translation_store.append((self.dest_button, 'Parcourir'))
        dest_layout.addLayout(dest_row)
        folders_row.addWidget(dest_container)

        folder_layout.addLayout(folders_row)
        parent_layout.addWidget(folder_container)
    
    def create_conversion_section(self, parent_layout):
        """Crée la section des boutons de conversion (responsive)"""
        # Import pour le scroll
        from PyQt6.QtWidgets import QScrollArea
        
        # Container principal pour les boutons avec scroll
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        conversion_container = QWidget()
        self.conversion_layout = QGridLayout(conversion_container)
        self.conversion_layout.setSpacing(20)
        
        # Stocker les groupes pour le redimensionnement
        self.button_groups = []
        
        # Colonne 1: Conversion
        conv_group = self.create_button_group(
            "Conversion",
            [
                ("CHD v5", self.convert_chd_v5, "#22c55e"),
                ("Extract CHD > BIN/CUE", self.extract_chd, "#22c55e"),
                ("Merge BIN/CUE", self.merge_bin_cue, "#22c55e"),
                ("GC/WII ISO to RVZ", self.convert_iso_rvz, "#22c55e"),
                ("WII ISO to WBFS", None, "#22c55e", True),  # Désactivé
                # Bouton PS1 to PSP EBOOT retiré
            ]
        )
        self.button_groups.append(conv_group)
        
        # Colonne 2: Compression / Décompression
        compress_group = self.create_button_group(
            "Compression / Décompression",
            [
                ("Compression wSquashFS", self.compress_wsquashfs, "#eab308"),
                ("Décompression wSquashFS", self.extract_wsquashfs, "#eab308")
            ]
        )
        self.button_groups.append(compress_group)
        
        # Colonne 3: Outils
        tools_group = self.create_button_group(
            "Outils",
            [
                ("Patch Xbox ISO", self.patch_xbox_iso, "#a855f7"),
                ("Infos CHD", self.show_chd_info, "#a855f7")
            ]
        )
        self.button_groups.append(tools_group)
        
        # Layout initial (3 colonnes)
        self.arrange_button_groups()
        
        scroll_area.setWidget(conversion_container)
        parent_layout.addWidget(scroll_area)
    
    def arrange_button_groups(self):
        """Arrange les groupes de boutons selon la taille de la fenêtre"""
        # Supprimer tous les widgets du layout
        for i in reversed(range(self.conversion_layout.count())):
            item = self.conversion_layout.itemAt(i)
            if item:
                child = item.widget()
                if child:
                    self.conversion_layout.removeWidget(child)

        # Charger les points de rupture depuis ui.json
        breakpoints = self.ui_config.get("window", {}).get("breakpoints", {})
        three_cols_breakpoint = breakpoints.get("threeCols", 1023)

        # Forcer 3 colonnes si la largeur est suffisante
        window_width = self.width()
        if window_width >= three_cols_breakpoint:
            for i, group in enumerate(self.button_groups):
                self.conversion_layout.addWidget(group, 0, i)
            self.conversion_layout.setSpacing(20)
        elif window_width >= breakpoints.get("twoCols", 800):
            for i, group in enumerate(self.button_groups):
                row = i // 2
                col = i % 2
                self.conversion_layout.addWidget(group, row, col)
            self.conversion_layout.setSpacing(15)
        else:
            for i, group in enumerate(self.button_groups):
                self.conversion_layout.addWidget(group, i, 0)
            self.conversion_layout.setSpacing(10)
        
        # Appliquer les styles responsifs
        self.apply_responsive_styles(window_width)
    
    def apply_responsive_styles(self, width):
        """Applique des styles responsifs selon la largeur"""
        if hasattr(self, 'conversion_buttons'):
            if width < 800:
                # Petits écrans - boutons plus compacts
                button_height = 35
                font_size = "14px"
            elif width < 1100:
                # Écrans moyens - taille normale
                button_height = 40
                font_size = "15px"
            else:
                # Grands écrans - boutons plus larges
                button_height = 45
                font_size = "16px"
            
            # Appliquer les styles à tous les boutons
            for button in self.conversion_buttons:
                button.setMinimumHeight(button_height)
                current_style = button.styleSheet()
                # Mettre à jour la taille de police dans le style
                if "font-size:" in current_style:
                    import re
                    new_style = re.sub(r'font-size:\s*\d+px', f'font-size: {font_size}', current_style)
                    button.setStyleSheet(new_style)
                
    def create_button_group(self, title, buttons):
        """Crée un groupe de boutons avec titre"""
        group_widget = QWidget()
        group_layout = QVBoxLayout(group_widget)
        group_layout.setSpacing(10)

        # Titre
        title_label = QLabel(title)
        title_label.setObjectName("buttonGroupTitle")
        group_layout.addWidget(title_label)
        self._translation_store.append((title_label, title))

        # Boutons
        self.conversion_buttons = getattr(self, 'conversion_buttons', [])
        for button_info in buttons:
            if len(button_info) == 3:
                text, callback, color = button_info
                disabled = False
            else:
                text, callback, color, disabled = button_info

            button = QPushButton(text)
            button.setObjectName("conversionButton")
            self._translation_store.append((button, text))
            color_class = None
            if color == self.ui_config["colors"]["green"]:
                color_class = "green"
            elif color == self.ui_config["colors"]["yellow"]:
                color_class = "yellow"
            elif color == self.ui_config["colors"]["purple"]:
                color_class = "purple"
            if color_class:
                button.setProperty("colorClass", color_class)
                button.setProperty("class", color_class)
            button.setMinimumHeight(40)

            if disabled:
                button.setEnabled(False)
                button.setProperty("disabled", True)
                button.setStyleSheet("")
            else:
                button.setProperty("disabled", False)
                if color_class:
                    button.setProperty("class", color_class)
                if callback:
                    button.clicked.connect(callback)
                self.conversion_buttons.append(button)
                # Conserver une référence spécifique pour logique d'activation différente
                if text == "Infos CHD":
                    self.chd_info_button = button
            group_layout.addWidget(button)
        group_layout.addStretch()
        return group_widget
    
    def create_footer(self, parent_layout):
        """Crée le footer avec version et bouton dark mode"""
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 20, 0, 0)

        # Version avec statut handlers
        app_version = getattr(QApplication.instance(), 'applicationVersion', lambda: "")( )
        version_text = f"RetroGameSets 2025 // Version {app_version}"
        version_label = QLabel(version_text)
        version_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        footer_layout.addWidget(version_label)

        footer_layout.addStretch()

        # Bouton dark mode
        self.dark_mode_button = QPushButton("Eteindre la lumière 🌙")
        self.dark_mode_button.clicked.connect(self.toggle_dark_mode)
        footer_layout.addWidget(self.dark_mode_button)
        self._translation_store.append((self.dark_mode_button, 'Eteindre la lumière 🌙'))

        # Switch langue (Combo compact)
        self.language_combo = QComboBox()
        self.language_combo.addItem('FR', 'fr')
        self.language_combo.addItem('EN', 'en')
        self.language_combo.setCurrentIndex(0)
        self.language_combo.setFixedWidth(60)
        self.language_combo.currentIndexChanged.connect(self.on_language_changed)
        footer_layout.addWidget(self.language_combo)

        parent_layout.addLayout(footer_layout)
    
    def darken_color(self, color):
        """Assombrit une couleur hexadécimale pour l'effet hover"""
        color_map = {
            "#22c55e": "#16a34a",  # green-500 -> green-600
            "#eab308": "#ca8a04",  # yellow-500 -> yellow-600
            "#a855f7": "#9333ea",  # purple-500 -> purple-600
            "#6b7280": "#4b5563"   # gray-500 -> gray-600
        }
        return color_map.get(color, color)
    
    def apply_styles(self):
        """Recharge et applique le QSS à chaque appel (chemin compatible PyInstaller)."""
        try:
            app = QApplication.instance()
            qss_path = resource_path(f"ressources/themes/{'dark.qss' if self.dark_mode else 'light.qss'}")
            if os.path.exists(qss_path):
                with open(qss_path, "r", encoding="utf-8") as f:
                    style = f.read()
                from PyQt6.QtWidgets import QApplication as QAppType
                if app is not None and isinstance(app, QAppType):
                    app.setStyleSheet("")
                    app.setStyleSheet(style)
                self.setStyleSheet("")
                self.setStyleSheet(style)
        except Exception as e:
            print(f"Erreur lors du chargement du fichier QSS : {e}")
    
    def toggle_dark_mode(self):
        """Bascule entre mode sombre et clair"""
        self.dark_mode = not self.dark_mode
        # Mettre à jour le texte suivant la langue
        if self.dark_mode:
            fr_text = "Allumer la lumière ☀️"
        else:
            fr_text = "Eteindre la lumière 🌙"
        if self.language == 'en':
            self.dark_mode_button.setText(self.translations_en.get(fr_text, fr_text))
        else:
            self.dark_mode_button.setText(fr_text)
        self.apply_styles()

    def on_language_changed(self):
        data = self.language_combo.currentData()
        if data in ('fr','en'):
            self.language = data
            self.retranslate_ui()
            self.save_settings()

    def retranslate_ui(self):
        """Applique les traductions aux widgets enregistrés."""
        for widget, base_text in self._translation_store:
            if isinstance(widget, QLineEdit):
                # Placeholder seulement
                if self.language == 'en':
                    widget.setPlaceholderText(self.translations_en.get(base_text, base_text))
                else:
                    widget.setPlaceholderText(base_text)
            else:
                if self.language == 'en':
                    widget.setText(self.translations_en.get(base_text, base_text))
                else:
                    widget.setText(base_text)
        # Retraduire la fenêtre de logs si ouverte
        if self.log_dialog:
            if self.language == 'en':
                self.log_dialog.setWindowTitle(self.translations_en.get('Logs de conversion', 'Conversion logs'))
                # Boutons spécifiques
                mapping = {
                    '🛑 Arrêter': '🛑 Stop',
                    '💾 Sauvegarder logs': '💾 Save logs',
                    'Ouvrir dossier LOG': 'Open LOG folder',
                    'Fermer': 'Close'
                }
                for child in self.log_dialog.findChildren(QPushButton):
                    base = None
                    # Trouver la clé FR correspondante
                    for fr, en in mapping.items():
                        if child.text() in (fr, en):
                            base = fr
                            break
                    if base:
                        child.setText(mapping[base])
            else:
                self.log_dialog.setWindowTitle('Logs de conversion')
                mapping = {
                    '🛑 Stop': '🛑 Arrêter',
                    '💾 Save logs': '💾 Sauvegarder logs',
                    'Open LOG folder': 'Ouvrir dossier LOG',
                    'Close': 'Fermer'
                }
                for child in self.log_dialog.findChildren(QPushButton):
                    if child.text() in mapping:
                        child.setText(mapping[child.text()])

    def translate_log_message(self, message: str) -> str:
        """Remplace les fragments FR par EN en conservant emojis et chiffres."""
        translated = message
        for fr, en in self.log_translations_en.items():
            if fr in translated:
                translated = translated.replace(fr, en)
        return translated
    
    def update_button_states(self):
        """Met à jour l'état des boutons selon la sélection des dossiers"""
        source_selected = bool(self.source_input.text())
        dest_selected = bool(self.dest_input.text())

        if hasattr(self, 'conversion_buttons'):
            for button in self.conversion_buttons:
                # Cas spécial: bouton Infos CHD actif avec seulement source
                if hasattr(self, 'chd_info_button') and button is self.chd_info_button:
                    enable = source_selected
                else:
                    enable = source_selected and dest_selected
                button.setEnabled(enable)
                color_class = button.property("colorClass")
                if enable:
                    button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                    if color_class:
                        button.setProperty("class", color_class)
                        button.setStyleSheet("")
                else:
                    button.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
                    button.setProperty("class", "")
                    button.setStyleSheet("")
    
    def resizeEvent(self, event):
        """Événement de redimensionnement - réarrange les boutons et adapte les marges"""
        super().resizeEvent(event)
        
        # Adapter les marges selon la taille de la fenêtre
        window_width = self.width()
        if window_width < 800:
            margin = 10
        elif window_width < 1000:
            margin = 20
        else:
            margin = 40
        
        # Mettre à jour les marges du layout principal
        try:
            central_widget = self.centralWidget()
            if central_widget:
                layout = central_widget.layout()
                if layout:
                    layout.setContentsMargins(margin, 20, margin, 20)
        except Exception:
            pass  # Ignorer les erreurs de layout
        
        # Réarranger les groupes de boutons si ils existent
        if hasattr(self, 'button_groups') and hasattr(self, 'conversion_layout'):
            self.arrange_button_groups()
    
    def select_source_folder(self):
        """Sélectionne le dossier source"""
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier source")
        if folder:
            self.source_folder = folder
            self.source_input.setText(folder)
    
    def select_dest_folder(self):
        """Sélectionne le dossier destination"""
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier destination")
        if folder:
            self.dest_folder = folder
            self.dest_input.setText(folder)
    
    def show_conversion_dialog(self, operation_name):
        """Affiche le dialog de conversion avec logs"""
        if not self.log_dialog:
            self.log_dialog = LogDialog(self)
        
        self.log_dialog.log_text.clear()
        self.log_dialog.hide_progress()
        # Traduction du titre d'opération
        op_title = operation_name
        if self.language == 'en':
            op_title = self.translations_en.get(operation_name, operation_name)
            prefix = 'Conversion - '
        else:
            prefix = 'Conversion - '
        self.log_dialog.setWindowTitle(f"{prefix}{op_title}")
        
        # Démarrer le worker thread
        self.current_worker = WorkerThread(operation_name, self.source_folder, self.dest_folder)
        
        # Connecter le worker à la dialog pour permettre l'arrêt
        self.log_dialog.set_worker_thread(self.current_worker)
        
        self.current_worker.progress_update.connect(self.log_dialog.update_progress)
        self.current_worker.log_message.connect(self.log_dialog.add_log)
        self.current_worker.finished.connect(self.on_conversion_finished)
        self.current_worker.finished.connect(self.log_dialog.on_finished)
        self.current_worker.start()
        
        self.log_dialog.show()
    
    def on_conversion_finished(self, results):
        """Appelé quand la conversion est terminée"""
        if self.log_dialog:
            self.log_dialog.hide_progress()
        self.current_worker = None
    
    # Méthodes de conversion (callbacks des boutons)
    def convert_chd_v5(self):
        self.show_conversion_dialog("Conversion CHD v5")
    def extract_chd(self):
        self.show_conversion_dialog("Extract CHD")
    
    def merge_bin_cue(self):
        self.show_conversion_dialog("Merge BIN/CUE")
    
    def convert_iso_rvz(self):
        self.show_conversion_dialog("Conversion ISO vers RVZ")
    
    def compress_wsquashfs(self):
        self.show_conversion_dialog("Compression wSquashFS")
    
    def extract_wsquashfs(self):
        self.show_conversion_dialog("Décompression wSquashFS")
    
    def patch_xbox_iso(self):
        self.show_conversion_dialog("Patch Xbox ISO")

    # ------------------ CHD INFO FEATURE ------------------
    def show_chd_info(self):
        """Analyse les fichiers .chd du dossier source et affiche un tableau d'infos."""
        if not self.source_input.text():
            return
        folder = Path(self.source_input.text())
        if not folder.exists():
            return
        chd_files = list(folder.glob('*.chd'))
        if not chd_files:
            # réutiliser la log dialog pour message rapide
            self.show_conversion_dialog("Conversion CHD v5")  # ouvre une dialog existante
            if self.log_dialog:
                msg = "Aucun fichier CHD trouvé" if self.language=='fr' else "No CHD file found"
                self.log_dialog.add_log(msg)
            return

        dialog = CHDInfoDialog(self)
        dialog.populate(chd_files, tools_path=Path('ressources'))
        dialog.exec()


class CHDInfoDialog(QDialog):
    """Dialog pour afficher les infos des CHD."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Infos CHD" if getattr(parent,'language','fr')=='fr' else 'CHD Info')
        self.resize(900, 400)
        layout = QVBoxLayout(self)
        from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        self.table = QTableWidget(0, 6)
        headers_fr = ["Fichier","Version","Type","Taille originale","Taille compressée","Ratio"]
        headers_en = ["File","Version","Type","Original size","Compressed size","Ratio"]
        lang = getattr(parent,'language','fr')
        self.table.setHorizontalHeaderLabels(headers_fr if lang=='fr' else headers_en)
        header = self.table.horizontalHeader()
        if header:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            # Largeurs par défaut (ajustables ensuite par l'utilisateur)
            default_widths = [250, 70, 60, 130, 140, 70]
            for i, w in enumerate(default_widths):
                if i < self.table.columnCount():
                    self.table.setColumnWidth(i, w)
            header.setStretchLastSection(False)
        layout.addWidget(self.table)
        btn_close = QPushButton("Fermer" if lang=='fr' else 'Close')
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def human(self, n):
        try:
            n = int(n)
            for unit in ['B','KB','MB','GB','TB']:
                if n < 1024:
                    return f"{n:.0f} {unit}" if unit=='B' else f"{n:.2f} {unit}"
                n /= 1024
            return f"{n:.2f} PB"
        except Exception:
            return str(n)

    def parse_info(self, text: str):
        version = None
        logical = None
        chd_size = None
        ratio = None
        chd_type = None
        # Regex lignes
        for line in text.splitlines():
            line=line.strip()
            if line.startswith('File Version:'):
                version = line.split(':',1)[1].strip()
            elif line.startswith('Logical size:'):
                logical = re.sub(r'[^0-9]','', line.split(':',1)[1])
            elif line.startswith('CHD size:'):
                chd_size = re.sub(r'[^0-9]','', line.split(':',1)[1])
            elif line.startswith('Ratio:'):
                ratio = line.split(':',1)[1].strip()
            elif line.startswith('Metadata:') and "Tag='DVD" in line:
                chd_type = 'DVD'
            elif line.startswith('Metadata:') and "TRACK:1" in line:
                chd_type = 'CD'
        if not chd_type:
            # heuristique: si logical size > 1.5GB => DVD
            try:
                if logical and int(logical) > 1500*1024*1024:
                    chd_type='DVD'
                else:
                    chd_type='CD'
            except Exception:
                chd_type='?'
        return version or '?', chd_type, logical, chd_size, ratio or '?'

    def populate(self, files, tools_path: Path):
        from PyQt6.QtWidgets import QTableWidgetItem
        chdman = tools_path / 'chdman.exe'
        for f in files:
            try:
                # Exécuter chdman info
                proc = subprocess.run([str(chdman), 'info', '--input', str(f)], capture_output=True, text=True, timeout=30)
                output = proc.stdout + '\n' + proc.stderr
                version, chd_type, logical, chd_size, ratio = self.parse_info(output)
            except Exception as e:
                version, chd_type, logical, chd_size, ratio = ('?','?',None,None,'?')
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row,0,QTableWidgetItem(f.name))
            self.table.setItem(row,1,QTableWidgetItem(version))
            self.table.setItem(row,2,QTableWidgetItem(chd_type))
            self.table.setItem(row,3,QTableWidgetItem(self.human(logical) if logical else '?'))
            self.table.setItem(row,4,QTableWidgetItem(self.human(chd_size) if chd_size else '?'))
            self.table.setItem(row,5,QTableWidgetItem(ratio))

def main():
    """Point d'entrée principal"""
    app = QApplication(sys.argv)
    app.setApplicationName("B2PC")
    app.setApplicationVersion(APP_VERSION)
    
    # Créer le dossier LOG s'il n'existe pas
    Path("LOG").mkdir(exist_ok=True)
    
    # Fenêtre principale
    window = B2PCMainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
