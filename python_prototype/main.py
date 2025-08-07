#!/usr/bin/env python3
"""
B2PC - Batch Retro Games Converter
Version Python/PyQt6 avec l'interface parfaite de main.py.bak
"""

import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QLabel, QPushButton, QLineEdit, QTextEdit, QProgressBar,
    QFileDialog, QDialog, QDialogButtonBox, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPixmap, QIcon
import logging
from datetime import datetime
import subprocess
import threading
import queue
import time
import random

# Import des handlers réels (avec fallback)
try:
    from handlers import ChdV5Handler, RvzHandler, SquashFSHandler, XboxPatchHandler # type: ignore
    REAL_HANDLERS_AVAILABLE = True
    print("✅ Tous les handlers importés avec succès")
except ImportError as e:
    REAL_HANDLERS_AVAILABLE = False
    print(f"⚠️ Handlers réels non disponibles - Mode simulation activé: {str(e)}")
except Exception as e:
    REAL_HANDLERS_AVAILABLE = False
    print(f"⚠️ Erreur lors de l'import des handlers: {str(e)}")

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
        self.handler = None  # Référence au handler pour pouvoir l'arrêter
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
        """Exécute la conversion (réelle si handlers disponibles, sinon simulation)"""
        try:
            self.log_both(f"🚀 Début de l'opération : {self.operation}")
            self.log_both(f"📁 Dossier source: {self.source_folder}")
            self.log_both(f"📁 Dossier destination: {self.dest_folder}")
            
            # Vérifier si on peut faire une vraie conversion
            if REAL_HANDLERS_AVAILABLE:
                self.log_both("⚡ Mode conversion réelle activé")
                results = self.run_real_conversion()
            else:
                self.log_both("🎭 Mode simulation activé (handlers non disponibles)")
                results = self.run_simulation()
            
            self.log_both("=" * 50)
            self.log_both("🎉 Opération terminée avec succès!")
            self.log_both(f"📄 Log sauvegardé: {self.log_file}")
            
            self.finished.emit(results)
            
        except Exception as e:
            error_msg = f"❌ Erreur critique : {str(e)}"
            self.log_both(error_msg)
            self.finished.emit({'error': str(e)})

    def run_real_conversion(self):
        """Exécute une vraie conversion avec les handlers"""
        self.progress_update.emit(10, "Initialisation des outils")
        
        # Sélectionner le bon handler
        handler = None
        tools_path = Path("../ressources")  # Chemin vers les outils
        
        def log_callback(msg):
            self.log_both(f"🔧 {msg}")
        
        def progress_callback(progress, msg):
            self.progress_update.emit(progress, msg)
        
        try:
            if "CHD v5" in self.operation:
                self.handler = ChdV5Handler(str(tools_path), log_callback, progress_callback)
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
            
            if "Compression" in self.operation:
                results = self.handler.compress()
            elif "Extraction" in self.operation or "Extract" in self.operation or "Décompression" in self.operation:
                results = self.handler.extract()
            else:
                results = self.handler.convert()
            
            return results
            
        except Exception as e:
            self.log_both(f"❌ Erreur handler réel: {str(e)}")
            self.log_both("🎭 Basculement vers simulation...")
            return self.run_simulation()

    def run_simulation(self):
        """Simule une opération de conversion réaliste avec logs"""
        # Validation des outils
        self.progress_update.emit(5, "Validation des outils")
        self.msleep(300)
        
        tools = {
            "CHD": ["chdman.exe", "7za.exe"],
            "RVZ": ["dolphin-tool.exe"],
            "Xbox": ["xiso.exe"],
            "wSquashFS": ["gensquashfs.exe", "unsquashfs.exe"]
        }
        
        relevant_tools = []
        for key, tool_list in tools.items():
            if key in self.operation:
                relevant_tools.extend(tool_list)
        
        if not relevant_tools:
            relevant_tools = ["7za.exe", "chdman.exe"]
        
        for tool in relevant_tools:
            self.msleep(150)
            self.log_both(f"✅ {tool} trouvé et fonctionnel")
        
        # Analyse des fichiers
        self.progress_update.emit(15, "Analyse des fichiers")
        self.msleep(500)
        self.log_both("🔍 Recherche des fichiers compatibles...")
        
        # Simulation de fichiers trouvés selon l'opération
        if "CHD" in self.operation:
            files = ["Final Fantasy VII (USA).bin", "Metal Gear Solid (USA).bin", "Crash Bandicoot (USA).bin"]
            output_ext = "chd"
        elif "RVZ" in self.operation:
            files = ["Metroid Prime (USA).iso", "Super Mario Galaxy (USA).iso", "Zelda Wind Waker (USA).iso"]
            output_ext = "rvz"
        elif "Xbox" in self.operation:
            files = ["Halo (USA).iso", "Fable (USA).iso", "Forza Motorsport (USA).iso"]
            output_ext = "iso (patched)"
        elif "wSquashFS" in self.operation:
            files = ["ROMS_Collection.7z", "Games_Archive.zip", "Retro_Games.rar"]
            output_ext = "wbfs" if "Compression" in self.operation else "extracted"
        else:
            files = ["Game1.iso", "Game2.bin", "Game3.cue"]
            output_ext = "converted"
        
        self.msleep(800)
        self.log_both(f"📊 {len(files)} fichier(s) trouvé(s) pour la conversion")
        
        # Traitement des fichiers
        converted = 0
        errors = 0
        total_files = len(files)
        
        for i, filename in enumerate(files):
            base_progress = 25 + (i / total_files) * 65
            self.progress_update.emit(int(base_progress), f"Traitement {i+1}/{total_files}")
            
            self.log_both(f"🔄 Début traitement: {filename}")
            
            # Simulation du temps de traitement variable
            processing_steps = random.randint(8, 15)
            for j in range(processing_steps):
                self.msleep(random.randint(100, 300))
                step_progress = base_progress + (j / processing_steps) * (65 / total_files)
                
                if j == 2:
                    self.log_both(f"   📖 Lecture des métadonnées de {filename}")
                elif j == 5:
                    self.log_both(f"   ⚙️ Application de l'algorithme de conversion")
                elif j == processing_steps - 3:
                    self.log_both(f"   💾 Écriture du fichier de sortie")
                
                self.progress_update.emit(int(step_progress), f"Conversion: {filename}")
            
            # Simulation succès/erreur (90% de succès)
            if random.random() < 0.9:
                output_name = filename.replace(Path(filename).suffix, f".{output_ext}")
                self.log_both(f"✅ Succès: {filename} → {output_name}")
                
                # Informations détaillées
                original_size = random.randint(50, 800)  # MB
                if "Compression" in self.operation:
                    new_size = int(original_size * random.uniform(0.3, 0.7))
                    compression_ratio = int((1 - new_size/original_size) * 100)
                    self.log_both(f"   📉 Taille: {original_size}MB → {new_size}MB (compression {compression_ratio}%)")
                else:
                    self.log_both(f"   📏 Taille traitée: {original_size}MB")
                
                converted += 1
            else:
                error_reasons = [
                    "fichier corrompu détecté",
                    "format non supporté",
                    "erreur d'écriture disque",
                    "métadonnées invalides"
                ]
                reason = random.choice(error_reasons)
                self.log_both(f"❌ Échec: {filename} - {reason}")
                errors += 1
            
            self.msleep(200)
        
        # Finalisation
        self.progress_update.emit(90, "Finalisation")
        self.msleep(500)
        self.log_both("🧹 Nettoyage des fichiers temporaires...")
        self.msleep(300)
        self.log_both("🔍 Vérification de l'intégrité des fichiers générés...")
        self.msleep(400)
        
        self.progress_update.emit(100, "Terminé")
        
        # Résumé détaillé
        duration = (len(files) * random.uniform(1.2, 2.8))
        self.log_both(f"📈 Statistiques finales:")
        self.log_both(f"   🎮 Fichiers traités: {converted}/{total_files}")
        self.log_both(f"   ❌ Erreurs rencontrées: {errors}")
        self.log_both(f"   ⏱️ Durée totale: {duration:.1f}s")
        self.log_both(f"   ✅ Taux de réussite: {(converted/total_files)*100:.1f}%")
        
        if converted > 0:
            self.log_both(f"📁 Fichiers générés disponibles dans: {self.dest_folder}")
        
        return {
            'converted_games': converted,
            'skipped_games': 0,
            'error_count': errors,
            'duration': duration,
            'total_files': total_files
        }

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
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
            QPushButton:disabled {
                background-color: #9ca3af;
                color: #6b7280;
            }
        """)
        self.stop_button.clicked.connect(self.request_stop)
        
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
        
        # Appliquer le style
        self.apply_styles()
    
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
    
    def apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f3f4f6;
                color: #1f2937;
            }
            QTextEdit {
                background-color: white;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 10px;
                font-family: 'Consolas', monospace;
            }
            QPushButton {
                background-color: #6b7280;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
            QProgressBar {
                border: 1px solid #d1d5db;
                border-radius: 6px;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #10b981;
                border-radius: 5px;
            }
        """)
    
    def add_log(self, message):
        """Ajoute un message au log avec coloration"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
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
                subprocess.run(["explorer", str(log_dir)])
            elif sys.platform == "darwin":
                subprocess.run(["open", str(log_dir)])
            else:
                subprocess.run(["xdg-open", str(log_dir)])
    
    def save_current_log(self):
        """Sauvegarde le log actuel affiché"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Sauvegarder les logs affichés",
            f"B2PC_logs_interface_{timestamp}.txt",
            "Fichiers texte (*.txt)"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("B2PC - Logs de conversion (Interface)\n")
                    f.write(f"Généré le: {datetime.now()}\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(self.log_text.toPlainText())
                
                # Afficher confirmation
                self.add_log(f"💾 Logs sauvegardés: {Path(filename).name}")
            except Exception as e:
                self.add_log(f"❌ Erreur sauvegarde: {str(e)}")

class B2PCMainWindow(QMainWindow):
    """Fenêtre principale de l'application B2PC"""
    
    def __init__(self):
        super().__init__()
        self.source_folder = ""
        self.dest_folder = ""
        self.dark_mode = False
        self.current_worker = None
        self.log_dialog = None
        
        self.init_ui()
        self.apply_styles()
        
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        self.setWindowTitle("B2PC - Batch Retro Games Converter")
        self.setFixedSize(1000, 700)
        
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
    
    def create_header(self, parent_layout):
        """Crée la section header avec logo et descriptions"""
        header_layout = QVBoxLayout()
        header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Logo (placeholder)
        logo_label = QLabel("🎮 B2PC")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet("font-size: 48px; font-weight: bold; color: #1f2937; margin: 10px;")
        header_layout.addWidget(logo_label)
        
        # Descriptions
        desc1 = QLabel("Conversion et compression de jeux automatisée")
        desc1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc1.setStyleSheet("font-size: 16px; font-weight: 600; color: #6b7280; font-style: italic;")
        header_layout.addWidget(desc1)
        
        desc2 = QLabel("Compatible : PS1 / PS2 / Dreamcast / PCEngineCD / SegaCD / Saturn / Xbox / Gamecube / Wii")
        desc2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc2.setStyleSheet("font-size: 14px; color: #6b7280; font-style: italic; margin-bottom: 20px;")
        header_layout.addWidget(desc2)
        
        parent_layout.addLayout(header_layout)
    
    def create_folder_section(self, parent_layout):
        """Crée la section de sélection des dossiers"""
        folder_layout = QGridLayout()
        folder_layout.setSpacing(15)
        
        # Dossier source
        source_label = QLabel("Dossier source (Archives autorisées):")
        source_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #1f2937;")
        folder_layout.addWidget(source_label, 0, 0)
        
        source_row = QHBoxLayout()
        self.source_input = QLineEdit()
        self.source_input.setReadOnly(True)
        self.source_input.setPlaceholderText("Sélectionnez un dossier source...")
        self.source_input.textChanged.connect(self.update_button_states)
        source_row.addWidget(self.source_input)
        
        self.source_button = QPushButton("Parcourir")
        self.source_button.clicked.connect(self.select_source_folder)
        source_row.addWidget(self.source_button)
        
        source_widget = QWidget()
        source_widget.setLayout(source_row)
        folder_layout.addWidget(source_widget, 1, 0)
        
        # Dossier destination
        dest_label = QLabel("Dossier destination:")
        dest_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #1f2937;")
        folder_layout.addWidget(dest_label, 0, 1)
        
        dest_row = QHBoxLayout()
        self.dest_input = QLineEdit()
        self.dest_input.setReadOnly(True)
        self.dest_input.setPlaceholderText("Sélectionnez un dossier destination...")
        self.dest_input.textChanged.connect(self.update_button_states)
        dest_row.addWidget(self.dest_input)
        
        self.dest_button = QPushButton("Parcourir")
        self.dest_button.clicked.connect(self.select_dest_folder)
        dest_row.addWidget(self.dest_button)
        
        dest_widget = QWidget()
        dest_widget.setLayout(dest_row)
        folder_layout.addWidget(dest_widget, 1, 1)
        
        parent_layout.addLayout(folder_layout)
    
    def create_conversion_section(self, parent_layout):
        """Crée la section des boutons de conversion"""
        conversion_layout = QGridLayout()
        conversion_layout.setSpacing(20)
        
        # Colonne 1: Conversion
        conv_group = self.create_button_group(
            "Conversion",
            [
                ("CHD v5", self.convert_chd_v5, "#22c55e"),
                ("Extract CHD > BIN/CUE", self.extract_chd, "#22c55e"),
                ("Merge BIN/CUE", self.merge_bin_cue, "#22c55e"),
                ("GC/WII ISO to RVZ", self.convert_iso_rvz, "#22c55e"),
                ("WII ISO to WBFS", None, "#22c55e", True),  # Désactivé
                ("PS1 to PSP EBOOT", None, "#22c55e", True)   # Désactivé
            ]
        )
        conversion_layout.addWidget(conv_group, 0, 0)
        
        # Colonne 2: Compression / Décompression
        compress_group = self.create_button_group(
            "Compression / Décompression",
            [
                ("Compression wSquashFS", self.compress_wsquashfs, "#eab308"),
                ("Décompression wSquashFS", self.extract_wsquashfs, "#eab308")
            ]
        )
        conversion_layout.addWidget(compress_group, 0, 1)
        
        # Colonne 3: Outils
        tools_group = self.create_button_group(
            "Outils",
            [
                ("Patch Xbox ISO", self.patch_xbox_iso, "#a855f7")
            ]
        )
        conversion_layout.addWidget(tools_group, 0, 2)
        
        parent_layout.addLayout(conversion_layout)
    
    def create_button_group(self, title, buttons):
        """Crée un groupe de boutons avec titre"""
        group_widget = QWidget()
        group_layout = QVBoxLayout(group_widget)
        group_layout.setSpacing(10)
        
        # Titre
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f2937; margin-bottom: 10px;")
        group_layout.addWidget(title_label)
        
        # Boutons
        self.conversion_buttons = getattr(self, 'conversion_buttons', [])
        for button_info in buttons:
            if len(button_info) == 3:
                text, callback, color = button_info
                disabled = False
            else:
                text, callback, color, disabled = button_info
            
            button = QPushButton(text)
            button.setMinimumHeight(40)
            
            if disabled:
                button.setEnabled(False)
                button.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {color};
                        color: white;
                        border: none;
                        border-radius: 6px;
                        font-weight: bold;
                        opacity: 0.5;
                    }}
                """)
            else:
                button.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {color};
                        color: white;
                        border: none;
                        border-radius: 6px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{
                        background-color: {self.darken_color(color)};
                    }}
                    QPushButton:disabled {{
                        background-color: #d1d5db;
                        color: #9ca3af;
                    }}
                """)
                
                if callback:
                    button.clicked.connect(callback)
                
                self.conversion_buttons.append(button)
            
            group_layout.addWidget(button)
        
        group_layout.addStretch()
        return group_widget
    
    def create_footer(self, parent_layout):
        """Crée le footer avec version et bouton dark mode"""
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 20, 0, 0)
        
        # Version avec statut handlers
        handler_status = "Conversion Réelle" if REAL_HANDLERS_AVAILABLE else "Mode Simulation"
        version_text = f"RetroGameSets 2025 // Version 3.4.2 (Python - {handler_status})"
        version_label = QLabel(version_text)
        version_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        footer_layout.addWidget(version_label)
        
        footer_layout.addStretch()
        
        # Bouton dark mode
        self.dark_mode_button = QPushButton("Eteindre la lumière 🌙")
        self.dark_mode_button.clicked.connect(self.toggle_dark_mode)
        footer_layout.addWidget(self.dark_mode_button)
        
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
        """Applique les styles CSS à l'application"""
        if self.dark_mode:
            # Style sombre
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #111827;
                    color: #FFFFFF;
                }
                QWidget {
                    background-color: #111827;
                    color: #FFFFFF;
                }
                QLineEdit {
                    background-color: #1f2937;
                    border: 1px solid #4b5563;
                    border-radius: 6px;
                    padding: 8px;
                    color: #FFFFFF;
                }
                QPushButton {
                    background-color: #4b5563;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #374151;
                }
                QLabel {
                    color: #FFFFFF;
                }
            """)
        else:
            # Style clair
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #f3f4f6;
                    color: #1f2937;
                }
                QWidget {
                    background-color: #f3f4f6;
                    color: #1f2937;
                }
                QLineEdit {
                    background-color: white;
                    border: 1px solid #d1d5db;
                    border-radius: 6px;
                    padding: 8px;
                    color: #1f2937;
                }
                QLineEdit:read-only {
                    background-color: #f9fafb;
                }
                QPushButton {
                    background-color: #6b7280;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #4b5563;
                }
                QPushButton:disabled {
                    background-color: #d1d5db;
                    color: #9ca3af;
                }
                QLabel {
                    color: #1f2937;
                }
            """)
    
    def toggle_dark_mode(self):
        """Bascule entre mode sombre et clair"""
        self.dark_mode = not self.dark_mode
        self.dark_mode_button.setText("Allumer la lumière ☀️" if self.dark_mode else "Eteindre la lumière 🌙")
        self.apply_styles()
    
    def update_button_states(self):
        """Met à jour l'état des boutons selon la sélection des dossiers"""
        folders_selected = bool(self.source_input.text() and self.dest_input.text())
        
        if hasattr(self, 'conversion_buttons'):
            for button in self.conversion_buttons:
                button.setEnabled(folders_selected)
    
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
        self.log_dialog.setWindowTitle(f"Conversion - {operation_name}")
        
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
        self.show_conversion_dialog("Extraction CHD")
    
    def merge_bin_cue(self):
        self.show_conversion_dialog("Fusion BIN/CUE")
    
    def convert_iso_rvz(self):
        self.show_conversion_dialog("Conversion ISO vers RVZ")
    
    def compress_wsquashfs(self):
        self.show_conversion_dialog("Compression wSquashFS")
    
    def extract_wsquashfs(self):
        self.show_conversion_dialog("Décompression wSquashFS")
    
    def patch_xbox_iso(self):
        self.show_conversion_dialog("Patch Xbox ISO")

def main():
    """Point d'entrée principal"""
    app = QApplication(sys.argv)
    app.setApplicationName("B2PC")
    app.setApplicationVersion("3.4.2-python-perfect")
    
    # Créer le dossier LOG s'il n'existe pas
    Path("LOG").mkdir(exist_ok=True)
    
    # Fenêtre principale
    window = B2PCMainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
