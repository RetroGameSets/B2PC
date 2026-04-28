APP_VERSION = "3.6.5.0"
UPDATE_URL = "https://raw.githubusercontent.com/RetroGameSets/B2PC/refs/heads/main/ressources/last_version.json"
DISCORD_URL = "https://discord.gg/chz59Z9Bhj"

import os
import sys
import urllib.request
import webbrowser
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QLabel, QPushButton, QLineEdit, QTextEdit, QProgressBar,
    QFileDialog, QDialog, QComboBox, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QCursor
from typing import Optional, Dict, Any
import logging
from datetime import datetime
import subprocess
from handlers.chdv5 import ChdV5Handler
from handlers.rvz import RvzHandler
from handlers.squashfs import SquashFSHandler
from handlers.xbox_patch import XboxPatchHandler
from handlers.extract_chd import ExtractChdHandler
from handlers.merge_bin_cue import MergeBinCueHandler
from handlers.ps3 import Ps3DecryptHandler
from handlers.wbfs_iso import WbfsIsoHandler
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

    def __init__(self, operation, source_folder, dest_folder, delete_source_after_conversion=False):
        super().__init__()
        self.operation = operation
        self.source_folder = source_folder
        self.dest_folder = dest_folder
        self.delete_source_after_conversion = delete_source_after_conversion
        self.log_file = None
        self.handler: Optional[ConversionHandler] = None  # Référence au handler pour pouvoir l'arrêter
        self.setup_logging()
    
    def stop_conversion(self):
        """Arrête la conversion en cours"""
        # Peut être appelé très tôt : assurer flag d'arrêt
        if self.handler:
            try:
                self.handler.stop_conversion()
            except Exception as e:
                self.log_both(f"⚠️ Erreur stop handler: {e}")
            else:
                self.log_both("🛑 Demande d'arrêt envoyée au handler")
        else:
            # Pas encore de handler instancié : simplement log + rien à tuer ici
            self.log_both("🛑 Demande d'arrêt enregistrée (handler non initialisé)")

    def setup_logging(self):
        """Configure le système de logging avec fichier"""
        # Créer le dossier LOG
        log_dir = Path("LOG")
        log_dir.mkdir(exist_ok=True)

        # Nom du fichier log avec timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Assainir le nom de l'opération pour un nom de fichier Windows (retirer caractères interdits)
        unsafe = str(self.operation)
        unsafe = unsafe.replace('/', '_')
        unsafe = re.sub(r'[<>:"/\\|?*]+', '_', unsafe)
        unsafe = re.sub(r'\s+', '_', unsafe).strip('_')
        operation_name = unsafe or 'Operation'

        log_filename = f"B2PC_{operation_name}_{timestamp}.log"
        self.log_file = log_dir / log_filename

        # Configurer le logger (éviter doublons)
        self.logger = logging.getLogger(f"B2PC_{operation_name}")
        self.logger.setLevel(logging.INFO)
        if self.logger.handlers:
            # Nettoyer anciens handlers (rare si réutilisation)
            for h in list(self.logger.handlers):
                self.logger.removeHandler(h)

        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
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
        """Exécute la conversion"""
        try:
            self.log_both(f"🚀 Début de l'opération : {self.operation}")
            self.log_both(f"📁 Dossier source: {self.source_folder}")
            self.log_both(f"📁 Dossier destination: {self.dest_folder}")
            
           
            results = self.run_conversion()

            error_count = 0
            has_error = False
            if isinstance(results, dict):
                has_error = bool(results.get('error'))
                try:
                    error_count = int(results.get('error_count', 0) or 0)
                except Exception:
                    error_count = 0

            self.log_both("=" * 50)
            if has_error:
                self.log_both("❌ Opération terminée avec erreur")
            elif error_count > 0:
                self.log_both(f"⚠️ Opération terminée avec {error_count} erreur(s)")
            else:
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
            if self.operation == "Conversion ISO/CUE/GDI > CHD":
                self.handler = ChdV5Handler(str(tools_path), log_callback, progress_callback)
            elif any(k in self.operation for k in ("Extraire CHD", "Extract CHD")):
                self.handler = ExtractChdHandler(str(tools_path), log_callback, progress_callback)
            elif "Merge BIN/CUE" in self.operation:
                self.handler = MergeBinCueHandler(str(tools_path), log_callback, progress_callback)
            elif "RVZ" in self.operation and "WBFS" not in self.operation:
                self.handler = RvzHandler(str(tools_path), log_callback, progress_callback)
                if "[GC/WII] RVZ > ISO" in self.operation:
                    self.handler.direction = "rvz_to_iso"
                else:
                    self.handler.direction = "iso_to_rvz"
            elif "wSquashFS" in self.operation:
                self.handler = SquashFSHandler(str(tools_path), log_callback, progress_callback)
            elif "Xbox" in self.operation:
                self.handler = XboxPatchHandler(str(tools_path), log_callback, progress_callback)
            elif "PS3" in self.operation:
                self.handler = Ps3DecryptHandler(str(tools_path), log_callback, progress_callback)
            elif any(k in self.operation for k in ("[WII] ISO > WBFS", "[WII] WBFS > ISO", "[WII] WBFS > RVZ", "[WII] WBFS <> ISO")):
                self.handler = WbfsIsoHandler(str(tools_path), log_callback, progress_callback)
                if "[WII] ISO > WBFS" in self.operation:
                    self.handler.direction = "iso_to_wbfs"
                elif "[WII] WBFS > RVZ" in self.operation:
                    self.handler.direction = "wbfs_to_rvz"
                elif "[WII] WBFS > ISO" in self.operation:
                    self.handler.direction = "wbfs_to_iso"
            else:
                raise ValueError(f"Handler non disponible pour: {self.operation}")

            # Configurer le handler
            self.handler.source_folder = self.source_folder
            self.handler.dest_folder = self.dest_folder
            self.handler.delete_source_after_conversion = self.delete_source_after_conversion

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
    # Titre par défaut (sera adapté ensuite)
        self.setWindowTitle("Logs")
        self.setModal(True)
        self.resize(800, 600)
        self.worker_thread = None  # Référence au thread worker
        self.stop_state = "ready"

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
        self.stop_button = QPushButton("🛑")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.clicked.connect(self.request_stop)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)

        self.open_log_folder_button = QPushButton("Open")
        self.open_log_folder_button.clicked.connect(self.open_log_folder)

        self.save_log_button = QPushButton("Save")
        self.save_log_button.clicked.connect(self.save_current_log)

        button_layout.addWidget(self.stop_button)
        button_layout.addStretch()
        button_layout.addWidget(self.save_log_button)
        button_layout.addWidget(self.open_log_folder_button)
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)
        self.apply_language(getattr(parent, 'language', 'fr'), parent)
        

    def set_worker_thread(self, worker_thread):
        """Définit la référence au thread worker pour pouvoir l'arrêter"""
        self.worker_thread = worker_thread
        
    def request_stop(self):
        """Demande l'arrêt de la conversion"""
        if self.worker_thread:
            self.stop_button.setEnabled(False)
            self.stop_state = "stopping"
            self.worker_thread.stop_conversion()
            self.add_log("🛑 Demande d'arrêt envoyée...")
            parent = self.parent()
            if parent and isinstance(parent, B2PCMainWindow):
                self.apply_language(parent.language, parent)
        
    def on_finished(self, results):
        """Appelé quand la conversion est terminée"""
        self.stop_button.setEnabled(False)
        self.stop_state = "done"
        parent = self.parent()
        if parent and isinstance(parent, B2PCMainWindow):
            self.apply_language(parent.language, parent)

        error_count = 0
        has_error = False
        if isinstance(results, dict):
            has_error = bool(results.get('error'))
            try:
                error_count = int(results.get('error_count', 0) or 0)
            except Exception:
                error_count = 0

        if isinstance(results, dict) and results.get('stopped', False):
            final_progress_text = "Stopped"
            if parent and isinstance(parent, B2PCMainWindow):
                final_progress_text = parent.tr('ui.progress.stopped', language=parent.language)
            self.add_log("🛑 Conversion arrêtée par l'utilisateur")
        elif has_error or error_count > 0:
            final_progress_text = "Finished with errors"
            if parent and isinstance(parent, B2PCMainWindow):
                final_progress_text = parent.tr('ui.progress.finished_with_errors', language=parent.language)
            self.add_log("⚠️ Conversion terminée avec erreurs")
        else:
            final_progress_text = "Done"
            if parent and isinstance(parent, B2PCMainWindow):
                final_progress_text = parent.tr('ui.progress.done', language=parent.language)
            self.add_log("✅ Conversion terminée")

        # Forcer un état final visible même si le dernier callback handler est partiel.
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat(final_progress_text)
    
    def add_log(self, message):
        """Ajoute un message au log avec coloration"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        parent = self.parent()
        if parent and isinstance(parent, B2PCMainWindow):
            if not parent.should_display_log_message(message):
                return

        # Traduction dynamique si interface en anglais
        # Vérification stricte du type pour éviter l'avertissement de l'analyseur statique
        if parent and isinstance(parent, B2PCMainWindow) and parent.language == 'en':
            # Appel direct garanti par isinstance
            message = parent.translate_log_message(message)  # type: ignore[attr-defined]

        is_dark_mode = bool(parent.dark_mode) if parent and isinstance(parent, B2PCMainWindow) else False
        is_accessibility_mode = bool(getattr(parent, 'theme_mode', '') == 'accessibility') if parent and isinstance(parent, B2PCMainWindow) else False
        
        # En mode accessibilité: monochrome (pas de codage couleur par type de message).
        if is_accessibility_mode:
            color = "#FFFFFF"
        elif "❌" in message or "Erreur" in message or "Échec" in message:
            color = "#dc2626"  # Rouge
        elif "⚠️" in message or "erreur(s)" in message or "avec erreurs" in message:
            color = "#eab308"  # Jaune
        elif "✅" in message or "Succès" in message or "terminée" in message:
            color = "#16a34a"  # Vert
        elif "⏳" in message or "🔄" in message or "Traitement" in message:
            color = "#eab308"  # Jaune
        elif "🎉" in message or "Statistiques" in message:
            color = "#8b5cf6"  # Violet
        else:
            # Les messages standards doivent rester lisibles en thème sombre.
            color = "#cbd5e1" if is_dark_mode else "#374151"
        
        formatted_message = f'<span style="color: {color};">[{timestamp}] {message}</span><br>'
        self.log_text.insertHtml(formatted_message)
        self.log_text.ensureCursorVisible()
    
    def update_progress(self, value, text):
        """Met à jour la barre de progression"""
        self.progress_bar.setVisible(True)
        display_value = int(value)
        match = re.search(r"(\d+)\s*/\s*(\d+)", text or "")
        if match:
            try:
                current = int(match.group(1))
                total = int(match.group(2))
                if total > 0:
                    # Progression par palier de fichier: 1/2 -> 0%, 2/2 -> 50%.
                    display_value = int(((current - 1) / total) * 100)
            except Exception:
                display_value = int(value)
        display_value = max(0, min(100, display_value))
        self.progress_bar.setValue(display_value)
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
        parent = self.parent() if isinstance(self.parent(), B2PCMainWindow) else None
        if parent and isinstance(parent, B2PCMainWindow):
            title = parent.tr('ui.log.save_dialog_title')
            file_filter = parent.tr('ui.log.save_dialog_filter')
            header_line = parent.tr('ui.log.file_header')
            generated_on = parent.tr('ui.log.generated_on')
            saved_prefix = parent.tr('ui.log.saved_prefix')
            save_error_prefix = parent.tr('ui.log.save_error_prefix')
        else:
            title = 'Save logs'
            file_filter = 'Text files (*.txt)'
            header_line = 'B2PC - Conversion logs (Interface)'
            generated_on = 'Generated on:'
            saved_prefix = '💾 Logs saved:'
            save_error_prefix = '❌ Save error:'

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename, _ = QFileDialog.getSaveFileName(
            self,
            title,
            f"B2PC_logs_interface_{timestamp}.txt",
            file_filter
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"{header_line}\n")
                    f.write(f"{generated_on} {datetime.now()}\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(self.log_text.toPlainText())
                
                # Afficher confirmation
                self.add_log(f"{saved_prefix} {Path(filename).name}")
            except Exception as e:
                self.add_log(f"{save_error_prefix} {str(e)}")

    def closeEvent(self, event):
        """Si une conversion est en cours, on masque juste la fenêtre pour pouvoir la réafficher."""
        if self.worker_thread and self.worker_thread.isRunning():
            event.ignore()
            self.hide()
        else:
            super().closeEvent(event)

    # --- Mise à jour langue ---
    def apply_language(self, language: str, main_window=None):
        """Met à jour les textes des boutons selon la langue."""
        if not main_window or not isinstance(main_window, B2PCMainWindow):
            return

        self.setWindowTitle(main_window.tr('ui.log.window_title', language=language))
        stop_key = 'ui.log.stop'
        if self.stop_state == 'stopping':
            stop_key = 'ui.log.stopping'
        elif self.stop_state == 'done':
            stop_key = 'ui.log.done'
        self.stop_button.setText(main_window.tr(stop_key, language=language))
        self.close_button.setText(main_window.tr('ui.common.close', language=language))
        self.save_log_button.setText(main_window.tr('ui.log.save_logs', language=language))
        self.open_log_folder_button.setText(main_window.tr('ui.log.open_folder', language=language))


class SettingsDialog(QDialog):
    """Dialog dédié aux réglages persistants de l'application."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setModal(True)
        self.resize(420, 330)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        self.title_label = QLabel("Settings")
        self.title_label.setObjectName("settingsTitle")
        layout.addWidget(self.title_label)

        theme_row = QHBoxLayout()
        self.theme_label = QLabel("Theme")
        theme_row.addWidget(self.theme_label)
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.addItem("Accessibility", "accessibility")
        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch()
        layout.addLayout(theme_row)

        self.remember_source_checkbox = QCheckBox("Remember source")
        self.remember_source_checkbox.toggled.connect(self.on_remember_source_toggled)
        layout.addWidget(self.remember_source_checkbox)

        self.delete_source_checkbox = QCheckBox("Delete source after conversion")
        self.delete_source_checkbox.toggled.connect(self.on_delete_source_toggled)
        layout.addWidget(self.delete_source_checkbox)

        log_level_row = QHBoxLayout()
        self.log_level_label = QLabel("Log level")
        log_level_row.addWidget(self.log_level_label)
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItem("Verbose", "verbose")
        self.log_level_combo.addItem("Errors only", "error_only")
        self.log_level_combo.currentIndexChanged.connect(self.on_log_level_changed)
        log_level_row.addWidget(self.log_level_combo)
        log_level_row.addStretch()
        layout.addLayout(log_level_row)

        language_row = QHBoxLayout()
        self.language_label = QLabel("Language")
        language_row.addWidget(self.language_label)
        self.language_combo = QComboBox()
        self.language_combo.addItem("FR", "fr")
        self.language_combo.addItem("EN", "en")
        self.language_combo.currentIndexChanged.connect(self.on_language_changed)
        language_row.addWidget(self.language_combo)
        language_row.addStretch()
        layout.addLayout(language_row)

        action_row = QHBoxLayout()
        self.support_button = QPushButton("Support")
        self.support_button.clicked.connect(self.open_support)
        action_row.addWidget(self.support_button)
        action_row.addStretch()

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        action_row.addWidget(self.close_button)
        layout.addLayout(action_row)

    def refresh_from_parent(self):
        if not self.main_window:
            return

        self.theme_combo.blockSignals(True)
        self.remember_source_checkbox.blockSignals(True)
        self.delete_source_checkbox.blockSignals(True)
        self.log_level_combo.blockSignals(True)
        self.language_combo.blockSignals(True)

        theme_index = self.theme_combo.findData(self.main_window.theme_mode)
        if theme_index >= 0:
            self.theme_combo.setCurrentIndex(theme_index)
        self.remember_source_checkbox.setChecked(bool(self.main_window.remember_folders))
        self.delete_source_checkbox.setChecked(bool(self.main_window.delete_source_after_conversion))
        log_level_index = self.log_level_combo.findData(self.main_window.screen_log_level)
        if log_level_index >= 0:
            self.log_level_combo.setCurrentIndex(log_level_index)
        index = self.language_combo.findData(self.main_window.language)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)

        self.theme_combo.blockSignals(False)
        self.remember_source_checkbox.blockSignals(False)
        self.delete_source_checkbox.blockSignals(False)
        self.log_level_combo.blockSignals(False)
        self.language_combo.blockSignals(False)

    def apply_language(self, language, main_window=None):
        if not main_window or not isinstance(main_window, B2PCMainWindow):
            return

        self.setWindowTitle(main_window.tr('ui.settings.title', language=language))
        self.title_label.setText(main_window.tr('ui.settings.title', language=language))
        self.theme_label.setText(main_window.tr('ui.settings.theme', language=language))
        self.theme_combo.setItemText(0, main_window.tr('ui.settings.theme_light', language=language))
        self.theme_combo.setItemText(1, main_window.tr('ui.settings.theme_dark', language=language))
        self.theme_combo.setItemText(2, main_window.tr('ui.settings.theme_accessibility', language=language))
        self.remember_source_checkbox.setText(main_window.tr('ui.settings.remember_source', language=language))
        self.delete_source_checkbox.setText(main_window.tr('ui.settings.delete_source', language=language))
        self.log_level_label.setText(main_window.tr('ui.settings.log_level', language=language))
        self.log_level_combo.setItemText(0, main_window.tr('ui.settings.log_level_verbose', language=language))
        self.log_level_combo.setItemText(1, main_window.tr('ui.settings.log_level_error_only', language=language))
        self.language_label.setText(main_window.tr('ui.settings.language', language=language))
        self.support_button.setText(main_window.tr('ui.settings.support', language=language))
        self.close_button.setText(main_window.tr('ui.common.close', language=language))

    def on_theme_changed(self):
        if self.main_window:
            mode = self.theme_combo.currentData()
            if mode in ('light', 'dark', 'accessibility'):
                self.main_window.set_theme_mode(str(mode))

    def on_remember_source_toggled(self, checked):
        if self.main_window:
            self.main_window.set_remember_source(checked)

    def on_delete_source_toggled(self, checked):
        if self.main_window:
            self.main_window.set_delete_source_after_conversion(checked)

    def on_log_level_changed(self):
        if self.main_window:
            level = self.log_level_combo.currentData()
            if level in ('verbose', 'error_only'):
                self.main_window.set_screen_log_level(str(level))

    def on_language_changed(self):
        if self.main_window:
            data = self.language_combo.currentData()
            if data in ('fr', 'en'):
                self.main_window.set_language(data)

    def open_support(self):
        webbrowser.open(DISCORD_URL)

class B2PCMainWindow(QMainWindow):
    """Fenêtre principale de l'application B2PC"""
    
    def __init__(self):
        super().__init__()
        self.source_folder = ""
        self.dest_folder = ""
        self.dark_mode = False
        self.theme_mode = "light"
        self.delete_source_after_conversion = False
        self.current_worker = None
        self.log_dialog = None
        self.settings_dialog = None
        # Charger paramétrage (langue) avant construction UI
        self.language = 'fr'
        self.remember_folders = True
        self.screen_log_level = 'error_only'
        self._settings = {}
        self._translation_store = []  # Liste de tuples (widget, i18n_key)
        self.translations_fr: Dict[str, str] = {}
        self.translations_en: Dict[str, str] = {}
        self.log_translations_fr: Dict[str, str] = {}
        self.log_translations_en: Dict[str, str] = {}
        self.operation_title_keys: Dict[str, str] = {
            "Conversion ISO/CUE/GDI > CHD": "ui.operation.chd_convert",
            "Extraire CHD": "ui.operation.extract_chd",
            "Merge BIN/CUE": "ui.operation.merge_bin_cue",
            "Conversion ISO vers RVZ": "ui.operation.iso_to_rvz",
            "wSquashFS Compression": "ui.operation.wsquashfs_compress",
            "wSquashFS Extraction": "ui.operation.wsquashfs_extract",
            "[XBOX] Patch ISO": "ui.operation.xbox_patch",
            "[PS3] Decrypt ISO & Convert": "ui.operation.ps3_decrypt",
            "[WII] ISO > WBFS": "ui.operation.wii_iso_to_wbfs",
            "[WII] WBFS > ISO": "ui.operation.wii_wbfs_to_iso",
            "[WII] WBFS > RVZ": "ui.operation.wii_wbfs_to_rvz",
            "[GC/WII] RVZ > ISO": "ui.operation.rvz_to_iso"
        }
        self.load_translations()

        # Charger les paramètres persistants puis configuration UI
        self._settings = self.load_settings()
        if isinstance(self._settings, dict):
            self.language = self._settings.get('language', 'fr')
            loaded_theme_mode = str(self._settings.get('theme_mode', '') or '').strip().lower()
            if loaded_theme_mode in ('light', 'dark', 'accessibility'):
                self.theme_mode = loaded_theme_mode
            else:
                self.theme_mode = 'dark' if bool(self._settings.get('dark_mode', False)) else 'light'
            self.dark_mode = self.theme_mode == 'dark'
            self.remember_folders = bool(self._settings.get('remember_folders', True))
            self.delete_source_after_conversion = bool(self._settings.get('delete_source_after_conversion', False))
            loaded_log_level = str(self._settings.get('screen_log_level', 'error_only') or '').strip().lower()
            self.screen_log_level = loaded_log_level if loaded_log_level in ('verbose', 'error_only') else 'error_only'
        # Charger la configuration UI
        self.ui_config = self.load_ui_config()

        self.init_ui()
        self.restore_folder_settings()
        self.apply_styles()
        # Appliquer la langue chargée
        if self.language == 'en':
            self.retranslate_ui()

    def load_translation_file(self, language: str) -> Dict[str, Any]:
        """Charge un fichier de traduction JSON depuis ressources/i18n."""
        try:
            path = resource_path(f"ressources/i18n/{language}.json")
            if not os.path.exists(path):
                return {}
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception as e:
            print(f"Erreur chargement traduction {language}: {e}")
        return {}

    def load_translations(self):
        """Charge les chaînes UI et logs depuis fr.json/en.json."""
        fr_data = self.load_translation_file('fr')
        en_data = self.load_translation_file('en')

        fr_ui = fr_data.get('ui', {}) if isinstance(fr_data, dict) else {}
        en_ui = en_data.get('ui', {}) if isinstance(en_data, dict) else {}
        fr_logs = fr_data.get('log_fragments', {}) if isinstance(fr_data, dict) else {}
        en_logs = en_data.get('log_fragments', {}) if isinstance(en_data, dict) else {}

        self.translations_fr = fr_ui if isinstance(fr_ui, dict) else {}
        self.translations_en = en_ui if isinstance(en_ui, dict) else {}
        self.log_translations_fr = fr_logs if isinstance(fr_logs, dict) else {}
        self.log_translations_en = en_logs if isinstance(en_logs, dict) else {}

    def tr(self, key: str, language: Optional[str] = None, default: Optional[str] = None) -> str:
        lang = language or self.language
        table = self.translations_en if lang == 'en' else self.translations_fr
        fallback = self.translations_fr

        if key in table:
            return str(table[key])
        if key in fallback:
            return str(fallback[key])
        if default is not None:
            return default
        return key

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
            source_saved = self.source_folder if self.remember_folders else ''
            data = {
                'language': self.language,
                'dark_mode': self.dark_mode,
                'theme_mode': self.theme_mode,
                'remember_folders': self.remember_folders,
                'delete_source_after_conversion': self.delete_source_after_conversion,
                'screen_log_level': self.screen_log_level,
                'source_folder': source_saved,
                'dest_folder': ''
            }
            with open(cfg_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_default_dest_for_source(self, source_folder: str) -> str:
        source_path = Path(source_folder)
        default_dest = source_path / "converted"
        try:
            default_dest.mkdir(parents=True, exist_ok=True)
        except Exception:
            return ""
        return str(default_dest)

    def apply_default_dest_if_empty(self, source_folder: str, persist: bool = True):
        if not source_folder:
            return
        if getattr(self, 'dest_input', None) and self.dest_input.text().strip():
            return

        default_dest = self.get_default_dest_for_source(source_folder)
        if not default_dest:
            return

        self.dest_folder = default_dest
        if getattr(self, 'dest_input', None):
            self.dest_input.setText(default_dest)
        if persist:
            self.save_settings()

    def restore_folder_settings(self):
        if not isinstance(self._settings, dict):
            return

        if not self.remember_folders:
            return

        saved_source = str(self._settings.get('source_folder', '') or '').strip()

        if saved_source and Path(saved_source).exists():
            self.source_folder = saved_source
            self.source_input.setText(saved_source)

        if self.source_folder and not self.dest_input.text().strip():
            self.apply_default_dest_if_empty(self.source_folder, persist=True)
    
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
        self.setWindowTitle(self.tr('ui.app.title', default='B2PC - Batch Retro Games Converter'))

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

        # Barre de progression globale (toujours visible dans la fenêtre principale)
        self.create_main_progress_section(main_layout)

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
        logo_label = QLabel(self.tr('ui.header.logo', default='🎮 B2PC'))
        logo_label.setObjectName("logoLabel")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(logo_label)
        self._translation_store.append((logo_label, 'ui.header.logo'))
        
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
        source_label = QLabel(self.tr('ui.folder.source.label', default='Dossier source (Archives autorisées):'))
        source_label.setObjectName("sourceLabel")
        source_layout.addWidget(source_label)
        self._translation_store.append((source_label, 'ui.folder.source.label'))
        source_row = QHBoxLayout()
        self.source_input = QLineEdit()
        self.source_input.setReadOnly(True)
        self.source_input.setPlaceholderText(self.tr('ui.folder.source.placeholder', default='Sélectionnez un dossier source...'))
        self._translation_store.append((self.source_input, 'ui.folder.source.placeholder'))
        self.source_input.textChanged.connect(self.update_button_states)
        source_row.addWidget(self.source_input)
        self.source_button = QPushButton(self.tr('ui.common.browse', default='Parcourir'))
        self.source_button.clicked.connect(self.select_source_folder)
        source_row.addWidget(self.source_button)
        self._translation_store.append((self.source_button, 'ui.common.browse'))
        source_layout.addLayout(source_row)
        folders_row.addWidget(source_container)

        # Destination
        dest_container = QWidget()
        dest_layout = QVBoxLayout(dest_container)
        dest_layout.setContentsMargins(0, 0, 0, 0)
        dest_label = QLabel(self.tr('ui.folder.dest.label', default='Dossier destination:'))
        dest_label.setObjectName("destLabel")
        dest_layout.addWidget(dest_label)
        self._translation_store.append((dest_label, 'ui.folder.dest.label'))
        dest_row = QHBoxLayout()
        self.dest_input = QLineEdit()
        self.dest_input.setReadOnly(True)
        self.dest_input.setPlaceholderText(self.tr('ui.folder.dest.placeholder', default='Sélectionnez un dossier destination...'))
        self._translation_store.append((self.dest_input, 'ui.folder.dest.placeholder'))
        self.dest_input.textChanged.connect(self.update_button_states)
        dest_row.addWidget(self.dest_input)
        self.dest_button = QPushButton(self.tr('ui.common.browse', default='Parcourir'))
        self.dest_button.clicked.connect(self.select_dest_folder)
        dest_row.addWidget(self.dest_button)
        self._translation_store.append((self.dest_button, 'ui.common.browse'))
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
            "ui.group.compression",
            [
                ("ui.button.iso_chd", self.convert_chd_v5, "#22c55e"),
                ("ui.button.wsquashfs_compress", self.compress_wsquashfs, "#eab308"),
                ("ui.button.iso_to_rvz", self.convert_iso_rvz, "#22c55e"),
                ("ui.button.iso_rvz_to_wbfs", self.convert_iso_to_wbfs, "#22c55e"),
                ("ui.button.wbfs_to_rvz", self.convert_wbfs_to_rvz, "#22c55e"),
            ]
        )
        self.button_groups.append(conv_group)
        
        # Colonne 2: Compression / Décompression
        compress_group = self.create_button_group(
            "ui.group.decompression",
            [
                ("ui.button.extract_chd", self.extract_chd, "#22c55e"),
                ("ui.button.wsquashfs_extract", self.extract_wsquashfs, "#eab308"),
                ("ui.button.rvz_to_iso", self.convert_rvz_to_iso, "#22c55e"),
                ("ui.button.wbfs_to_iso", self.convert_wbfs_to_iso, "#22c55e"),
            ]
        )
        self.button_groups.append(compress_group)
        
        # Colonne 3: Outils
        tools_group = self.create_button_group(
            "ui.group.tools",
            [
                ("ui.button.chd_info", self.show_chd_info, "#a855f7"),
                ("ui.button.xbox_patch", self.patch_xbox_iso, "#a855f7"),
                ("ui.button.merge_bin_cue", self.merge_bin_cue, "#22c55e"),
                ("ui.button.ps3_decrypt", self.decrypt_ps3_iso, "#a855f7")
            ]
        )
        self.button_groups.append(tools_group)
        
        # Layout initial (3 colonnes)
        self.arrange_button_groups()
        
        scroll_area.setWidget(conversion_container)
        parent_layout.addWidget(scroll_area)

    def create_main_progress_section(self, parent_layout):
        """Crée la barre de progression principale de l'application."""
        self.main_progress_bar = QProgressBar()
        self.main_progress_bar.setVisible(False)
        self.main_progress_bar.setValue(0)
        self.main_progress_bar.setFormat("")
        parent_layout.addWidget(self.main_progress_bar)

    def update_main_progress(self, value: int, text: str):
        """Met à jour la progression affichée dans la fenêtre principale."""
        if not hasattr(self, 'main_progress_bar'):
            return
        safe_value = int(value)
        match = re.search(r"(\d+)\s*/\s*(\d+)", text or "")
        if match:
            try:
                current = int(match.group(1))
                total = int(match.group(2))
                if total > 0:
                    # Même logique que dans la fenêtre de logs.
                    safe_value = int(((current - 1) / total) * 100)
            except Exception:
                safe_value = int(value)
        safe_value = max(0, min(100, safe_value))
        self.main_progress_bar.setVisible(True)
        self.main_progress_bar.setValue(safe_value)
        self.main_progress_bar.setFormat(text)

    def finalize_main_progress(self, results):
        """Force l'état final de la barre principale à 100% avec un texte explicite."""
        if not hasattr(self, 'main_progress_bar'):
            return

        progress_text = self.tr('ui.progress.done', default='Done')
        if isinstance(results, dict) and results.get('stopped', False):
            progress_text = self.tr('ui.progress.stopped', default='Stopped')
        else:
            try:
                error_count = int(results.get('error_count', 0) or 0) if isinstance(results, dict) else 0
            except Exception:
                error_count = 0
            has_error = bool(results.get('error')) if isinstance(results, dict) else False
            if has_error or error_count > 0:
                progress_text = self.tr('ui.progress.finished_with_errors', default='Finished with errors')

        self.main_progress_bar.setVisible(True)
        self.main_progress_bar.setValue(100)
        self.main_progress_bar.setFormat(progress_text)

    def hide_main_progress(self):
        """Masque la progression principale en fin d'opération."""
        if not hasattr(self, 'main_progress_bar'):
            return
        self.main_progress_bar.setVisible(False)
        self.main_progress_bar.setValue(0)
        self.main_progress_bar.setFormat("")
    
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
                
    def create_button_group(self, title_key, buttons):
        """Crée un groupe de boutons avec titre"""
        group_widget = QWidget()
        group_layout = QVBoxLayout(group_widget)
        group_layout.setSpacing(10)

        # Titre
        title_label = QLabel(self.tr(title_key, default=title_key))
        title_label.setObjectName("buttonGroupTitle")
        group_layout.addWidget(title_label)
        self._translation_store.append((title_label, title_key))

        # Boutons
        self.conversion_buttons = getattr(self, 'conversion_buttons', [])
        # Couleur forcée par groupe (évite d'avoir à répéter dans chaque tuple)
        group_color_override = None
        try:
            colors_cfg = self.ui_config.get("colors", {})
            if title_key == "ui.group.compression":
                group_color_override = colors_cfg.get("green", "#22c55e")
            elif title_key == "ui.group.decompression":
                group_color_override = colors_cfg.get("yellow", "#eab308")
            elif title_key == "ui.group.tools":
                group_color_override = colors_cfg.get("purple", "#a855f7")
        except Exception:
            group_color_override = None

        for button_info in buttons:
            if len(button_info) == 3:
                text_key, callback, color = button_info
                disabled = False
            else:
                text_key, callback, color, disabled = button_info

            if group_color_override:
                color = group_color_override

            button = QPushButton(self.tr(text_key, default=text_key))
            button.setObjectName("conversionButton")
            self._translation_store.append((button, text_key))
            color_class = None
            if color == self.ui_config["colors"].get("green"):
                color_class = "green"
            elif color == self.ui_config["colors"].get("yellow"):
                color_class = "yellow"
            elif color == self.ui_config["colors"].get("purple"):
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
                if text_key == "ui.button.chd_info":
                    self.chd_info_button = button
            group_layout.addWidget(button)
        group_layout.addStretch()
        return group_widget
    
    def create_footer(self, parent_layout):
        """Crée le footer avec version et actions permanentes."""
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 20, 0, 0)

        # Version avec statut handlers
        app_version = getattr(QApplication.instance(), 'applicationVersion', lambda: "")( )
        version_text = f"RetroGameSets 2025 // Version {app_version}"
        version_label = QLabel(version_text)
        version_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        footer_layout.addWidget(version_label)

        footer_layout.addStretch()

        # Bouton logs (accessible en permanence)
        self.show_logs_button = QPushButton(self.tr('ui.footer.show_logs', default='Afficher logs'))
        self.show_logs_button.clicked.connect(self.show_logs_dialog)
        footer_layout.addWidget(self.show_logs_button)
        self._translation_store.append((self.show_logs_button, 'ui.footer.show_logs'))

        self.settings_button = QPushButton(self.tr('ui.footer.settings', default='⚙ Réglages'))
        self.settings_button.setObjectName("settingsButton")
        self.settings_button.clicked.connect(self.open_settings_dialog)
        footer_layout.addWidget(self.settings_button)
        self._translation_store.append((self.settings_button, 'ui.footer.settings'))

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
            theme_file = 'light.qss'
            if self.theme_mode == 'dark':
                theme_file = 'dark.qss'
            elif self.theme_mode == 'accessibility':
                theme_file = 'accessibility.qss'

            qss_path = resource_path(f"ressources/themes/{theme_file}")
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
        self.set_theme_mode('light' if self.dark_mode else 'dark')

    def set_dark_mode(self, enabled: bool):
        self.set_theme_mode('dark' if bool(enabled) else 'light')

    def set_theme_mode(self, mode: str):
        normalized = str(mode or '').strip().lower()
        if normalized not in ('light', 'dark', 'accessibility'):
            normalized = 'light'

        self.theme_mode = normalized
        self.dark_mode = normalized == 'dark'
        self.apply_styles()
        self.save_settings()

    def set_language(self, language_code: str):
        if language_code not in ('fr', 'en'):
            return
        self.language = language_code
        self.retranslate_ui()
        self.save_settings()

    def set_remember_source(self, enabled: bool):
        self.remember_folders = bool(enabled)
        self.save_settings()

    def set_delete_source_after_conversion(self, enabled: bool):
        self.delete_source_after_conversion = bool(enabled)
        self.save_settings()

    def set_screen_log_level(self, level: str):
        normalized = str(level or '').strip().lower()
        if normalized not in ('verbose', 'error_only'):
            normalized = 'error_only'
        self.screen_log_level = normalized
        self.save_settings()

    def should_display_log_message(self, message: str) -> bool:
        """Filtre les logs affichés à l'écran selon le niveau choisi."""
        if self.screen_log_level != 'error_only':
            return True

        text = str(message or '')
        allowed_tokens = (
            '📄 Fichier:',
            '📄 Traitement direct:',
            '✅',
            '🎉',
            '❌',
            '⚠️',
            '🛑',
        )
        return any(token in text for token in allowed_tokens)

    def retranslate_ui(self):
        """Applique les traductions aux widgets enregistrés."""
        for widget, text_key in self._translation_store:
            if isinstance(widget, QLineEdit):
                widget.setPlaceholderText(self.tr(text_key, default=text_key))
            else:
                widget.setText(self.tr(text_key, default=text_key))

        self.setWindowTitle(self.tr('ui.app.title', default='B2PC - Batch Retro Games Converter'))
        # Retraduire la fenêtre de logs si ouverte en utilisant sa méthode dédiée
        if self.log_dialog:
            self.log_dialog.apply_language(self.language, self)
        if self.settings_dialog:
            self.settings_dialog.apply_language(self.language, self)

    def translate_log_message(self, message: str) -> str:
        """Remplace les fragments FR par EN en conservant emojis et chiffres."""
        if self.language != 'en':
            return message

        translated = message
        for key, fr_fragment in self.log_translations_fr.items():
            en_fragment = self.log_translations_en.get(key)
            if not en_fragment:
                continue
            if fr_fragment in translated:
                translated = translated.replace(fr_fragment, en_fragment)
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
        folder = QFileDialog.getExistingDirectory(self, self.tr('ui.folder.source.select_dialog', default='Sélectionner le dossier source'))
        if folder:
            self.source_folder = folder
            self.source_input.setText(folder)
            self.apply_default_dest_if_empty(folder)
            self.save_settings()
    
    def select_dest_folder(self):
        """Sélectionne le dossier destination"""
        folder = QFileDialog.getExistingDirectory(self, self.tr('ui.folder.dest.select_dialog', default='Sélectionner le dossier destination'))
        if folder:
            self.dest_folder = folder
            self.dest_input.setText(folder)
            self.save_settings()
    
    def show_conversion_dialog(self, operation_name):
        """Affiche le dialog de conversion avec logs"""
        if self.source_input.text().strip() and not self.dest_input.text().strip():
            self.apply_default_dest_if_empty(self.source_input.text().strip())

        if not self.log_dialog:
            self.log_dialog = LogDialog(self)
        # Appliquer langue actuelle aux boutons (y compris états des boutons)
        self.log_dialog.apply_language(self.language, self)

        # Reset contenu
        self.log_dialog.log_text.clear()
        self.log_dialog.hide_progress()

        # Traduction du titre d'opération
        op_title = operation_name
        op_key = self.operation_title_keys.get(operation_name)
        if op_key:
            op_title = self.tr(op_key, default=operation_name)
        prefix = 'Conversion - '
        self.log_dialog.setWindowTitle(f"{prefix}{op_title}")

        # Démarrer un nouveau worker
        self.current_worker = WorkerThread(
            operation_name,
            self.source_folder,
            self.dest_folder,
            delete_source_after_conversion=self.delete_source_after_conversion,
        )
        self.log_dialog.set_worker_thread(self.current_worker)

        self.update_main_progress(0, "Initialisation...")
        self.current_worker.progress_update.connect(self.log_dialog.update_progress)
        self.current_worker.progress_update.connect(self.update_main_progress)
        self.current_worker.log_message.connect(self.log_dialog.add_log)
        self.current_worker.finished.connect(self.on_conversion_finished)
        self.current_worker.finished.connect(self.log_dialog.on_finished)
        self.current_worker.start()

        self.log_dialog.show()

    def show_logs_dialog(self):
        """Affiche ou crée la fenêtre de logs sans démarrer une nouvelle conversion."""
        if not self.log_dialog:
            self.log_dialog = LogDialog(self)
        # Toujours appliquer traduction courante (titre + boutons)
        self.log_dialog.apply_language(self.language, self)
        # Ajuster titre simple si pas en cours de conversion
        self.log_dialog.setWindowTitle(self.tr('ui.log.window_title', default='Logs de conversion'))
        self.log_dialog.show()
        self.log_dialog.raise_()
        self.log_dialog.activateWindow()

    def open_settings_dialog(self):
        if not self.settings_dialog:
            self.settings_dialog = SettingsDialog(self)
        self.settings_dialog.refresh_from_parent()
        self.settings_dialog.apply_language(self.language, self)
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()
    
    def on_conversion_finished(self, results):
        """Appelé quand la conversion est terminée"""
        self.finalize_main_progress(results)
        self.current_worker = None
    
    # Méthodes de conversion (callbacks des boutons)
    def convert_chd_v5(self):
        self.show_conversion_dialog("Conversion ISO/CUE/GDI > CHD")
    def extract_chd(self):
        # Utiliser l'intitulé FR comme clé de traduction
        self.show_conversion_dialog("Extraire CHD")
    
    def merge_bin_cue(self):
        self.show_conversion_dialog("Merge BIN/CUE")
    
    def convert_iso_rvz(self):
        self.show_conversion_dialog("Conversion ISO vers RVZ")

    def convert_rvz_to_iso(self):
        self.show_conversion_dialog("[GC/WII] RVZ > ISO")
    
    def compress_wsquashfs(self):
        self.show_conversion_dialog("wSquashFS Compression")
    
    def extract_wsquashfs(self):
        self.show_conversion_dialog("wSquashFS Extraction")
    
    def patch_xbox_iso(self):
        self.show_conversion_dialog("[XBOX] Patch ISO")

    def decrypt_ps3_iso(self):
        self.show_conversion_dialog("[PS3] Decrypt ISO & Convert")

    def convert_iso_to_wbfs(self):
        self.show_conversion_dialog("[WII] ISO > WBFS")

    def convert_wbfs_to_iso(self):
        self.show_conversion_dialog("[WII] WBFS > ISO")

    def convert_wbfs_to_rvz(self):
        self.show_conversion_dialog("[WII] WBFS > RVZ")

    # Compatibilite eventuelle avec d'anciens liens UI
    def convert_wbfs_iso(self):
        self.show_conversion_dialog("[WII] WBFS > ISO")

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
            # Afficher simplement la fenêtre de logs sans démarrer de conversion
            self.show_logs_dialog()
            if self.log_dialog:
                self.log_dialog.add_log(self.tr('ui.chdinfo.no_file', default='Aucun fichier CHD trouvé'))
            return

        dialog = CHDInfoDialog(self)
        dialog.populate(chd_files, tools_path=Path('ressources'))
        dialog.exec()


class CHDInfoDialog(QDialog):
    """Dialog pour afficher les infos des CHD."""
    def __init__(self, parent=None):
        super().__init__(parent)
        p = parent if isinstance(parent, B2PCMainWindow) else None
        title = p.tr('ui.chdinfo.title', default='Infos CHD') if p else 'Infos CHD'
        self.setWindowTitle(title)
        self.resize(900, 400)
        layout = QVBoxLayout(self)
        from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        self.table = QTableWidget(0, 6)
        if p:
            headers = [
                p.tr('ui.chdinfo.header.file', default='Fichier'),
                p.tr('ui.chdinfo.header.version', default='Version'),
                p.tr('ui.chdinfo.header.type', default='Type'),
                p.tr('ui.chdinfo.header.original_size', default='Taille originale'),
                p.tr('ui.chdinfo.header.compressed_size', default='Taille compressée'),
                p.tr('ui.chdinfo.header.ratio', default='Ratio')
            ]
        else:
            headers = ["Fichier", "Version", "Type", "Taille originale", "Taille compressée", "Ratio"]
        self.table.setHorizontalHeaderLabels(headers)
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
        btn_close = QPushButton(p.tr('ui.common.close', default='Fermer') if p else 'Fermer')
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
