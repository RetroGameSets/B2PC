"""
Handlers pour les opérations de conversion B2PC
Équivalents Python des handlers JavaScript originaux
"""

import subprocess
import os
import shutil
import re
import tempfile
from pathlib import Path
from typing import List
import logging
from typing import List, Callable, Optional, Union

class ConversionHandler:
    """Classe de base pour tous les handlers de conversion"""
    
    def __init__(self, tools_path: Optional[str] = None, log_callback: Optional[Callable] = None, progress_callback: Optional[Callable] = None):
        self.tools_path = Path(tools_path) if tools_path else Path("../ressources")
        self.log = log_callback if log_callback else print
        self.progress = progress_callback if progress_callback else lambda p, m: None
        self.source_folder = ""
        self.dest_folder = ""
        self.temp_extract_folder = None
        self.should_stop = False  # Flag pour arrêter la conversion
        self.current_process = None  # Référence au processus en cours
        
    def validate_tools(self) -> bool:
        """Valide que tous les outils requis sont présents"""
        required_tools = [
            "7za.exe", "chdman.exe", "dolphin-tool.exe", 
            "xiso.exe", "gensquashfs.exe", "unsquashfs.exe"
        ]
        
        for tool in required_tools:
            tool_path = self.tools_path / tool
            if not tool_path.exists():
                self.log(f"❌ Outil manquant : {tool}")
                return False
                
        self.log("✅ Tous les outils sont présents")
        return True
    
    def stop_conversion(self):
        """Arrête la conversion en cours"""
        self.should_stop = True
        self.log("🛑 Arrêt de la conversion demandé...")
        
        # Terminer le processus en cours si il existe
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
                self.log("🛑 Processus terminé")
            except Exception as e:
                self.log(f"⚠️ Erreur lors de l'arrêt du processus: {str(e)}")
                try:
                    self.current_process.kill()
                    self.log("🛑 Processus forcé à s'arrêter")
                except Exception as e2:
                    self.log(f"❌ Impossible d'arrêter le processus: {str(e2)}")
    
    def check_should_stop(self) -> bool:
        """Vérifie si la conversion doit être arrêtée"""
        if self.should_stop:
            self.log("🛑 Conversion arrêtée par l'utilisateur")
            return True
        return False
    
    def run_tool(self, tool_name: str, args: List[str], cwd: Optional[str] = None, show_output: bool = True) -> bool:
        """Exécute un outil externe avec gestion d'erreurs et progression en temps réel"""
        
        # Vérifier si on doit arrêter avant de commencer
        if self.check_should_stop():
            return False
            
        tool_path = self.tools_path / tool_name
        
        try:
            cmd = [str(tool_path)] + args
            self.log(f"🔧 Exécution : {' '.join(cmd)}")
            
            if show_output:
                # Mode temps réel avec extraction de progression
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,  # Rediriger stderr vers stdout
                    cwd=cwd,
                    text=True,
                    bufsize=1,  # Line buffered
                    universal_newlines=True
                )
                
                # Lire la sortie ligne par ligne en temps réel
                if self.current_process.stdout:
                    while True:
                        # Vérifier si on doit arrêter
                        if self.check_should_stop():
                            self.current_process.terminate()
                            return False
                            
                        line = self.current_process.stdout.readline()
                        if line:
                            line = line.strip()
                            if line:
                                # Extraire la progression des outils
                                progress_value = self._extract_progress(line, tool_name)
                                if progress_value is not None:
                                    # Mettre à jour la barre de progression
                                    self.progress(progress_value, f"{tool_name}: {progress_value:.1f}%")
                                elif self._is_important_message(line, tool_name):
                                    # Logger seulement les messages importants
                                    self.log(f"   {line}")
                        elif self.current_process.poll() is not None:
                            break
                
                # Attendre que le processus se termine complètement
                self.current_process.wait()
                
            else:
                # Mode classique sans sortie temps réel
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=cwd,
                    text=True
                )
                
                stdout, stderr = self.current_process.communicate()
            
            # Vérifier si arrêté par l'utilisateur
            if self.check_should_stop():
                return False
                
            if self.current_process.returncode == 0:
                self.log(f"✅ {tool_name} terminé avec succès")
                return True
            else:
                if not show_output:
                    self.log(f"❌ Erreur {tool_name}: {stderr if 'stderr' in locals() else 'Erreur inconnue'}")
                else:
                    self.log(f"❌ {tool_name} terminé avec erreur (code: {self.current_process.returncode})")
                return False
                
        except Exception as e:
            self.log(f"❌ Exception lors de l'exécution de {tool_name}: {str(e)}")
            return False
        finally:
            self.current_process = None
    
    def _extract_progress(self, line: str, tool_name: str) -> Optional[float]:
        """Extrait le pourcentage de progression d'une ligne de sortie"""
        import re
        
        # Patterns pour différents outils - CORRIGÉ pour capturer tous les chiffres
        patterns = {
            "chdman.exe": [
                r"(\d+(?:\.\d+)?)%\s+complete",  # "15% complete" ou "15.5% complete"
                r"Compression:\s*(\d+(?:\.\d+)?)%",  # "Compression: 15%" ou "Compression: 15.5%"
                r"(\d+(?:\.\d+)?)%",  # Pattern générique pour tout pourcentage
            ],
            "dolphin-tool.exe": [
                r"(\d+(?:\.\d+)?)%",  # Progression générale
            ],
            "7za.exe": [
                r"(\d+(?:\.\d+)?)%",  # Progression d'extraction/compression
            ]
        }
        
        if tool_name in patterns:
            for pattern in patterns[tool_name]:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    try:
                        return float(match.group(1))
                    except (ValueError, IndexError):
                        continue
        
        return None
    
    def _is_important_message(self, line: str, tool_name: str) -> bool:
        """Détermine si un message doit être loggé (messages importants seulement)"""
        
        # Messages importants génériques
        important_keywords = [
            "complete", "completed", "finished", "done", "success",
            "error", "failed", "warning", "exception",
            "final ratio", "compression ratio", "total time",
            "created", "extracted", "converted"
        ]
        
        # Messages spécifiques par outil
        tool_keywords = {
            "chdman.exe": [
                "compression complete", "final ratio", "created"
            ],
            "dolphin-tool.exe": [
                "successfully converted", "conversion complete"
            ],
            "7za.exe": [
                "everything is ok", "files", "folders"
            ]
        }
        
        line_lower = line.lower()
        
        # Ignorer les lignes de progression pure (juste des %)
        if re.match(r"^\s*\d+%\s*$", line):
            return False
        
        # Vérifier les mots-clés importants
        for keyword in important_keywords:
            if keyword in line_lower:
                return True
        
        # Vérifier les mots-clés spécifiques à l'outil
        if tool_name in tool_keywords:
            for keyword in tool_keywords[tool_name]:
                if keyword in line_lower:
                    return True
        
        return False
    
    def detect_archives(self, folder_path: Path) -> List[Path]:
        """Détecte les archives ZIP/RAR/7Z dans le dossier"""
        archive_extensions = [".zip", ".rar", ".7z"]
        archives = []
        
        for ext in archive_extensions:
            archives.extend(list(folder_path.rglob(f"*{ext}")))
        
        if archives:
            self.log(f"📦 Détecté {len(archives)} archive(s) à extraire")
            for archive in archives:
                self.log(f"   📁 {archive.name}")
        
        return archives
    
    def extract_archive(self, archive_path: Path, extract_to: Path) -> bool:
        """Extrait une archive avec 7za.exe"""
        extract_to.mkdir(exist_ok=True)
        
        # Commande 7za pour extraction
        args = [
            "x",  # extract with full paths
            str(archive_path),
            f"-o{extract_to}",  # output directory
            "-y"  # assume Yes on all queries
        ]
        
        self.log(f"📂 Extraction: {archive_path.name} → {extract_to.name}")
        
        if self.run_tool("7za.exe", args):
            self.log(f"✅ Archive extraite: {archive_path.name}")
            return True
        else:
            self.log(f"❌ Échec extraction: {archive_path.name}")
            return False
    
    def get_all_source_files(self, file_extension: str) -> List[tuple]:
        """Retourne tous les fichiers sources (directs + dans archives) avec leurs chemins d'extraction"""
        source_path = Path(self.source_folder)
        files_list = []
        
        # 1. Fichiers directs (non dans des archives)
        direct_files = list(source_path.rglob(f"*{file_extension}"))
        for file_path in direct_files:
            files_list.append((file_path, None))  # None = pas d'extraction nécessaire
        
        # 2. Fichiers dans les archives
        archives = self.detect_archives(source_path)
        for archive in archives:
            files_list.append((archive, "archive"))  # "archive" = nécessite extraction
        
        return files_list
    
    def extract_single_archive(self, archive_path: Path) -> Path:
        """Extrait une seule archive dans un dossier temporaire et retourne le chemin"""
        if not self.temp_extract_folder:
            import tempfile
            self.temp_extract_folder = Path(tempfile.mkdtemp(prefix="B2PC_extract_"))
            self.log(f"📂 Dossier temporaire créé: {self.temp_extract_folder}")
        
        # Créer un sous-dossier pour cette archive
        archive_extract_folder = self.temp_extract_folder / f"extracted_{archive_path.stem}"
        
        if self.extract_archive(archive_path, archive_extract_folder):
            return archive_extract_folder
        else:
            raise Exception(f"Échec extraction de {archive_path.name}")
    
    def prepare_source_folder(self) -> str:
        """DEPRECATED: Utiliser get_all_source_files() pour le traitement fichier par fichier"""
        # Méthode conservée pour compatibilité avec SquashFSHandler qui traite des dossiers
        source_path = Path(self.source_folder)
        
        # Détecter les archives
        archives = self.detect_archives(source_path)
        
        if not archives:
            self.log("📁 Aucune archive détectée, utilisation directe du dossier source")
            return self.source_folder
        
        # Créer dossier temporaire pour extraction
        import tempfile
        self.temp_extract_folder = Path(tempfile.mkdtemp(prefix="B2PC_extract_"))
        self.log(f"📂 Dossier temporaire créé: {self.temp_extract_folder}")
        
        # Copier d'abord tous les fichiers non-archive
        self.log("📋 Copie des fichiers non-archive...")
        for item in source_path.rglob("*"):
            if item.is_file() and item.suffix.lower() not in [".zip", ".rar", ".7z"]:
                # Créer la structure de dossiers relative
                relative_path = item.relative_to(source_path)
                dest_file = self.temp_extract_folder / relative_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest_file)
        
        # Extraire toutes les archives
        extracted_count = 0
        for archive in archives:
            # Créer un sous-dossier pour chaque archive
            archive_extract_folder = self.temp_extract_folder / f"extracted_{archive.stem}"
            
            if self.extract_archive(archive, archive_extract_folder):
                extracted_count += 1
        
        self.log(f"📊 Extraction terminée: {extracted_count}/{len(archives)} archives extraites")
        
        if extracted_count > 0:
            self.log(f"✅ Utilisation du dossier temporaire: {self.temp_extract_folder}")
            return str(self.temp_extract_folder)
        else:
            # Si aucune extraction n'a réussi, utiliser le dossier original
            self.log("⚠️ Aucune extraction réussie, utilisation du dossier source original")
            return self.source_folder
    
    def cleanup_temp_folder(self):
        """Nettoie le dossier temporaire d'extraction"""
        if self.temp_extract_folder and self.temp_extract_folder.exists():
            try:
                shutil.rmtree(self.temp_extract_folder)
                self.log(f"🧹 Dossier temporaire nettoyé: {self.temp_extract_folder}")
            except Exception as e:
                self.log(f"⚠️ Erreur nettoyage dossier temporaire: {str(e)}")
            finally:
                self.temp_extract_folder = None

class ChdV5Handler(ConversionHandler):
    """Handler pour conversion vers CHD v5"""
    
    def convert(self) -> dict:
        """Convertit les ISOs en CHD v5 avec extraction à la volée"""
        
        dest_path = Path(self.dest_folder)
        dest_path.mkdir(exist_ok=True)
        
        try:
            # Obtenir tous les fichiers sources (directs + dans archives)
            source_files = self.get_all_source_files(".iso")
            
            self.log(f"📁 Trouvé {len(source_files)} sources à traiter")
            
            converted = 0
            errors = 0
            
            for i, (source_item, extract_type) in enumerate(source_files):
                # Vérifier si on doit arrêter
                if self.check_should_stop():
                    break
                    
                self.progress((i / len(source_files)) * 100, f"Traitement {i+1}/{len(source_files)}")
                
                if extract_type is None:
                    # Fichier direct
                    iso_files = [source_item]
                    self.log(f"📄 Traitement direct: {source_item.name}")
                    
                elif extract_type == "archive":
                    # Archive à extraire
                    self.log(f"📦 Extraction de l'archive: {source_item.name}")
                    try:
                        extracted_folder = self.extract_single_archive(source_item)
                        iso_files = list(extracted_folder.rglob("*.iso"))
                        self.log(f"📁 Trouvé {len(iso_files)} ISOs dans l'archive")
                    except Exception as e:
                        self.log(f"❌ Échec extraction {source_item.name}: {str(e)}")
                        errors += 1
                        continue
                
                # Convertir chaque ISO trouvé
                for iso_file in iso_files:
                    # Vérifier si on doit arrêter
                    if self.check_should_stop():
                        break
                        
                    chd_file = dest_path / f"{iso_file.stem}.chd"
                    
                    # Éviter la reconversion
                    if chd_file.exists():
                        self.log(f"⏭️ Fichier déjà converti : {chd_file.name}")
                        continue
                    
                    # Commande chdman
                    args = [
                        "createcd",
                        "-i", str(iso_file),
                        "-o", str(chd_file)
                    ]
                    
                    # Utiliser la sortie temps réel pour chdman (progression)
                    if self.run_tool("chdman.exe", args, show_output=True):
                        converted += 1
                        self.log(f"✅ Converti : {iso_file.name} → {chd_file.name}")
                    else:
                        errors += 1
                        self.log(f"❌ Échec conversion : {iso_file.name}")
                        
                # Arrêter la boucle externe si demandé
                if self.check_should_stop():
                    break
            
            # Message final selon l'état
            if self.should_stop:
                self.log("🛑 Conversion arrêtée par l'utilisateur")
            
            return {
                "converted_games": converted,
                "error_count": errors,
                "total_files": len(source_files),
                "stopped": self.should_stop
            }
            
        finally:
            # Nettoyer le dossier temporaire
            self.cleanup_temp_folder()

class RvzHandler(ConversionHandler):
    """Handler pour conversion ISO vers RVZ (GameCube/Wii)"""
    
    def convert(self) -> dict:
        """Convertit les ISOs GameCube/Wii en RVZ avec extraction à la volée"""
        
        dest_path = Path(self.dest_folder)
        dest_path.mkdir(exist_ok=True)
        
        try:
            # Obtenir tous les fichiers sources (directs + dans archives)
            source_files = self.get_all_source_files(".iso")
            
            self.log(f"🎮 Traitement de {len(source_files)} sources GameCube/Wii")
            
            converted = 0
            errors = 0
            
            for i, (source_item, extract_type) in enumerate(source_files):
                # Vérifier si on doit arrêter
                if self.check_should_stop():
                    break
                    
                self.progress((i / len(source_files)) * 100, f"Traitement RVZ {i+1}/{len(source_files)}")
                
                if extract_type is None:
                    # Fichier direct
                    iso_files = [source_item]
                    self.log(f"📄 Traitement direct: {source_item.name}")
                    
                elif extract_type == "archive":
                    # Archive à extraire
                    self.log(f"📦 Extraction de l'archive: {source_item.name}")
                    try:
                        extracted_folder = self.extract_single_archive(source_item)
                        iso_files = list(extracted_folder.rglob("*.iso"))
                        self.log(f"📁 Trouvé {len(iso_files)} ISOs dans l'archive")
                    except Exception as e:
                        self.log(f"❌ Échec extraction {source_item.name}: {str(e)}")
                        errors += 1
                        continue
                
                # Convertir chaque ISO trouvé
                for iso_file in iso_files:
                    # Vérifier si on doit arrêter
                    if self.check_should_stop():
                        break
                        
                    rvz_file = dest_path / f"{iso_file.stem}.rvz"
                    
                    if rvz_file.exists():
                        self.log(f"⏭️ RVZ déjà existant : {rvz_file.name}")
                        continue
                    
                    # Commande dolphin-tool
                    args = [
                        "convert",
                        "-f", "rvz",
                        "-c", "zstd",
                        "-l", "5",
                        "-i", str(iso_file),
                        "-o", str(rvz_file)
                    ]
                    
                    # Utiliser la sortie temps réel pour dolphin-tool
                    if self.run_tool("dolphin-tool.exe", args, show_output=True):
                        converted += 1
                        self.log(f"🐬 Converti en RVZ : {iso_file.name}")
                    else:
                        errors += 1
                        self.log(f"❌ Échec RVZ : {iso_file.name}")
                        
                # Arrêter la boucle externe si demandé
                if self.check_should_stop():
                    break
            
            # Message final selon l'état
            if self.should_stop:
                self.log("🛑 Conversion arrêtée par l'utilisateur")
            
            return {
                "converted_games": converted,
                "error_count": errors,
                "total_files": len(source_files),
                "stopped": self.should_stop
            }
            
        finally:
            # Nettoyer le dossier temporaire
            self.cleanup_temp_folder()

class XboxPatchHandler(ConversionHandler):
    """Handler pour patch des ISOs Xbox"""
    
    def convert(self) -> dict:
        """Patch les ISOs Xbox avec xiso - extraction à la volée"""
        
        dest_path = Path(self.dest_folder)
        dest_path.mkdir(exist_ok=True)
        
        try:
            # Obtenir tous les fichiers sources (directs + dans archives)
            source_files = self.get_all_source_files(".iso")
            
            self.log(f"🎮 Traitement de {len(source_files)} sources Xbox")
            
            patched = 0
            errors = 0
            
            for i, (source_item, extract_type) in enumerate(source_files):
                # Vérifier si on doit arrêter
                if self.check_should_stop():
                    break
                    
                self.progress((i / len(source_files)) * 100, f"Traitement Xbox {i+1}/{len(source_files)}")
                
                if extract_type is None:
                    # Fichier direct
                    iso_files = [source_item]
                    self.log(f"📄 Traitement direct: {source_item.name}")
                    
                elif extract_type == "archive":
                    # Archive à extraire
                    self.log(f"📦 Extraction de l'archive: {source_item.name}")
                    try:
                        extracted_folder = self.extract_single_archive(source_item)
                        iso_files = list(extracted_folder.rglob("*.iso"))
                        self.log(f"📁 Trouvé {len(iso_files)} ISOs dans l'archive")
                    except Exception as e:
                        self.log(f"❌ Échec extraction {source_item.name}: {str(e)}")
                        errors += 1
                        continue
                
                # Patcher chaque ISO trouvé
                for iso_file in iso_files:
                    # Vérifier si on doit arrêter
                    if self.check_should_stop():
                        break
                        
                    # Copier l'ISO dans le dossier destination
                    dest_iso = dest_path / iso_file.name
                    shutil.copy2(iso_file, dest_iso)
                    
                    # Patch avec xiso
                    args = ["-r", str(dest_iso)]
                    
                    if self.run_tool("xiso.exe", args, cwd=str(dest_path)):
                        patched += 1
                        self.log(f"🔧 ISO Xbox patché : {iso_file.name}")
                        
                        # Nettoyer tous les fichiers temporaires créés par xiso
                        self._cleanup_xbox_temp_files(dest_path, iso_file.name)
                    else:
                        errors += 1
                        self.log(f"❌ Échec patch Xbox : {iso_file.name}")
                        
                        # En cas d'échec, nettoyer aussi les fichiers temporaires
                        self._cleanup_xbox_temp_files(dest_path, iso_file.name)
                        
                # Arrêter la boucle externe si demandé
                if self.check_should_stop():
                    break
            
            # Message final selon l'état
            if self.should_stop:
                self.log("🛑 Conversion arrêtée par l'utilisateur")
            
            return {
                "converted_games": patched,
                "error_count": errors,
                "total_files": len(source_files),
                "stopped": self.should_stop
            }
            
        finally:
            # Nettoyer le dossier temporaire
            self.cleanup_temp_folder()
    
    def _cleanup_xbox_temp_files(self, dest_path: Path, iso_filename: str):
        """Nettoie tous les fichiers temporaires créés par xiso.exe"""
        
        # Patterns de fichiers temporaires créés par xiso
        temp_patterns = [
            f"{iso_filename}.old",      # Fichier backup principal
            f"{iso_filename}.bak",      # Fichier backup alternatif
            f"{iso_filename}.tmp",      # Fichier temporaire
            f"~{iso_filename}",         # Fichier temporaire avec préfixe ~
        ]
        
        cleaned_files = []
        
        for pattern in temp_patterns:
            temp_file = dest_path / pattern
            if temp_file.exists():
                try:
                    temp_file.unlink()
                    cleaned_files.append(pattern)
                    self.log(f"🧹 Fichier temporaire supprimé : {pattern}")
                except Exception as e:
                    self.log(f"⚠️ Impossible de supprimer {pattern}: {str(e)}")
        
        # Rechercher d'autres fichiers temporaires avec des patterns génériques
        try:
            # Rechercher les fichiers avec extensions temporaires
            for temp_file in dest_path.glob(f"{Path(iso_filename).stem}.*"):
                if temp_file.suffix.lower() in ['.tmp', '.temp', '.backup', '.bk']:
                    try:
                        temp_file.unlink()
                        cleaned_files.append(temp_file.name)
                        self.log(f"🧹 Fichier temporaire supprimé : {temp_file.name}")
                    except Exception as e:
                        self.log(f"⚠️ Impossible de supprimer {temp_file.name}: {str(e)}")
        except Exception:
            pass  # Ignorer les erreurs de recherche de patterns
        
        if cleaned_files:
            self.log(f"✅ Nettoyage terminé: {len(cleaned_files)} fichier(s) temporaire(s) supprimé(s)")
        else:
            self.log("ℹ️ Aucun fichier temporaire à nettoyer")

class SquashFSHandler(ConversionHandler):
    """Handler pour compression/décompression wSquashFS"""
    
    def get_all_source_files(self, source_path: str = "") -> List[str]:
        """Retourne tous les dossiers sources pour compression SquashFS"""
        if not source_path:
            source_path = self.source_folder
        
        source_dir = Path(source_path)
        source_files = []
        
        # Tous les dossiers directs (peu importe leur nom/extension apparente)
        for item in source_dir.iterdir():
            if item.is_dir():
                source_files.append(str(item))
        
        return source_files
    
    def compress(self) -> dict:
        """Compresse avec wSquashFS - traitement intelligent des sources"""
        
        dest_path = Path(self.dest_folder)
        dest_path.mkdir(exist_ok=True)
        
        try:
            # Obtenir tous les fichiers/dossiers sources
            source_path = Path(self.source_folder)
            
            # Détecter les archives d'abord
            archives = self.detect_archives(source_path)
            
            # Collecter tous les éléments à compresser
            items_to_compress = []
            
            # 1. Tous les dossiers directs (peu importe leur nom/extension apparente)
            for item in source_path.iterdir():
                if item.is_dir():
                    items_to_compress.append((item, None, "folder"))
                    self.log(f"📁 Dossier trouvé: {item.name}")
            
            # 2. Archives à extraire
            for archive in archives:
                items_to_compress.append((archive, "archive", "archive"))
                self.log(f"📦 Archive trouvée: {archive.name}")
            
            self.log(f"📦 Compression de {len(items_to_compress)} éléments")
            
            compressed = 0
            errors = 0
            
            for i, (source_item, extract_type, item_type) in enumerate(items_to_compress):
                # Vérifier si on doit arrêter
                if self.check_should_stop():
                    break
                    
                # Convertir en Path si c'est une string
                if isinstance(source_item, str):
                    source_item = Path(source_item)
                    
                self.progress((i / len(items_to_compress)) * 100, f"Compression {i+1}/{len(items_to_compress)}")
                
                if item_type == "folder":
                    # Dossier direct - compresser directement
                    self.log(f"📁 Compression dossier: {source_item.name}")
                    squashfs_file = dest_path / f"{source_item.name}.wsquashfs"
                    if self._compress_folder(source_item, squashfs_file):
                        compressed += 1
                    else:
                        errors += 1
                        
                elif item_type == "archive":
                    # Archive à extraire et compresser
                    self.log(f"📦 Extraction puis compression de l'archive: {source_item.name}")
                    try:
                        extracted_folder = self.extract_single_archive(source_item)
                        
                        # Trouver tous les dossiers dans l'archive extraite
                        for extracted_item in extracted_folder.iterdir():
                            if extracted_item.is_dir():
                                # Compresser le dossier extrait
                                squashfs_file = dest_path / f"{extracted_item.name}.wsquashfs"
                                if self._compress_folder(extracted_item, squashfs_file):
                                    compressed += 1
                                else:
                                    errors += 1
                                    
                    except Exception as e:
                        self.log(f"❌ Échec extraction archive {source_item.name}: {str(e)}")
                        errors += 1
                        continue
            
            # Message final selon l'état
            if self.should_stop:
                self.log("🛑 Compression arrêtée par l'utilisateur")
            
            return {
                "converted_games": compressed,
                "error_count": errors,
                "total_files": len(items_to_compress),
                "stopped": self.should_stop
            }
            
        finally:
            # Nettoyer le dossier temporaire
            self.cleanup_temp_folder()
    
    def _compress_folder(self, folder_path: Path, output_file: Path) -> bool:
        """Compresse un dossier avec gensquashfs - syntaxe JavaScript corrigée"""
        
        # Éviter la reconversion
        if output_file.exists():
            self.log(f"⏭️ Archive déjà existante : {output_file.name}")
            return True
        
        # Vérifier si on doit arrêter
        if self.check_should_stop():
            return False
        
        self.log(f"📦 Compression du dossier: {folder_path.name}")
        
        # Commande gensquashfs - SYNTAXE JAVASCRIPT CORRIGÉE
        args = [
            "--pack-dir", str(folder_path), str(output_file),
            "--compressor", "zstd",
            "--block-size", "1048576",
            "--num-jobs", "8"
        ]
        
        self.log(f"🔧 Commande: gensquashfs.exe {' '.join(args)}")
        
        if self.run_tool("gensquashfs.exe", args):
            self.log(f"✅ Compressé : {folder_path.name} → {output_file.name}")
            return True
        else:
            self.log(f"❌ Échec compression : {folder_path.name}")
            return False
    
    def extract(self) -> dict:
        """Décompresse les archives wSquashFS avec syntaxe JavaScript corrigée"""
        
        dest_path = Path(self.dest_folder)
        dest_path.mkdir(exist_ok=True)
        
        try:
            # Obtenir tous les fichiers sources (directs + dans archives)
            source_files = self.get_all_source_files_extract(".wsquashfs")
            
            self.log(f"📂 Traitement de {len(source_files)} sources SquashFS")
            
            extracted = 0
            errors = 0
            
            for i, (source_item, extract_type) in enumerate(source_files):
                # Vérifier si on doit arrêter
                if self.check_should_stop():
                    break
                    
                # Convertir en Path si c'est une string
                if isinstance(source_item, str):
                    source_item = Path(source_item)
                    
                self.progress((i / len(source_files)) * 100, f"Extraction {i+1}/{len(source_files)}")
                
                if extract_type is None:
                    # Fichier direct .wsquashfs
                    squashfs_files = [source_item]
                    self.log(f"📄 Extraction directe: {source_item.name}")
                    
                elif extract_type == "archive":
                    # Archive contenant des .wsquashfs
                    self.log(f"📦 Extraction de l'archive: {source_item.name}")
                    try:
                        extracted_folder = self.extract_single_archive(source_item)
                        squashfs_files = list(extracted_folder.rglob("*.wsquashfs"))
                        self.log(f"📁 Trouvé {len(squashfs_files)} fichiers SquashFS dans l'archive")
                    except Exception as e:
                        self.log(f"❌ Échec extraction archive {source_item.name}: {str(e)}")
                        errors += 1
                        continue
                
                # Extraire chaque fichier SquashFS trouvé
                for squashfs_file in squashfs_files:
                    # Vérifier si on doit arrêter
                    if self.check_should_stop():
                        break
                        
                    # Convertir en Path si nécessaire
                    if isinstance(squashfs_file, str):
                        squashfs_file = Path(squashfs_file)
                        
                    extract_dir = dest_path / squashfs_file.stem
                    
                    if extract_dir.exists():
                        self.log(f"⏭️ Dossier déjà extrait : {extract_dir.name}")
                        continue
                    
                    # Commande unsquashfs - SYNTAXE JAVASCRIPT CORRIGÉE
                    args = [
                        "--unpack-path", "/",              # Extraire tout le contenu
                        "--unpack-root", str(extract_dir), # Dossier de destination  
                        str(squashfs_file)                 # Fichier .wsquashfs
                    ]
                    
                    self.log(f"🔧 Commande: unsquashfs.exe {' '.join(args)}")
                    
                    if self.run_tool("unsquashfs.exe", args):
                        extracted += 1
                        self.log(f"📂 Extrait : {squashfs_file.name} → {extract_dir.name}")
                    else:
                        errors += 1
                        self.log(f"❌ Échec extraction : {squashfs_file.name}")
                        
                # Arrêter la boucle externe si demandé
                if self.check_should_stop():
                    break
            
            # Message final selon l'état
            if self.should_stop:
                self.log("🛑 Extraction arrêtée par l'utilisateur")
            
            return {
                "converted_games": extracted,
                "error_count": errors,
                "total_files": len(source_files),
                "stopped": self.should_stop
            }
            
        finally:
            # Nettoyer le dossier temporaire
            self.cleanup_temp_folder()
    
    def get_all_source_files_extract(self, file_extension: str) -> list:
        """Version corrigée pour extraction - retourne les .wsquashfs"""
        source_path = Path(self.source_folder)
        files_list = []
        
        # 1. Fichiers directs .wsquashfs
        direct_files = list(source_path.rglob(f"*{file_extension}"))
        for file_path in direct_files:
            files_list.append((str(file_path), None))  # None = pas d'extraction d'archive nécessaire
        
        # 2. Archives contenant potentiellement des .wsquashfs
        archives = self.detect_archives(source_path)
        for archive in archives:
            files_list.append((str(archive), "archive"))  # "archive" = nécessite extraction
        
        return files_list
    
    def convert(self) -> dict:
        """Méthode unifiée pour compatibilité avec l'interface principale"""
        # Pour SquashFS, on peut faire compression ou extraction selon les fichiers présents
        
        source_path = Path(self.source_folder)
        
        # Vérifier si on a des fichiers .wsquashfs (extraction) ou des dossiers (compression)  
        wsquashfs_files = list(source_path.rglob("*.wsquashfs"))
        directories = [item for item in source_path.iterdir() if item.is_dir()]
        
        if wsquashfs_files:
            # Mode extraction
            self.log("🔍 Fichiers .wsquashfs détectés → Mode extraction")
            return self.extract()
        elif directories:
            # Mode compression  
            self.log("📁 Dossiers détectés → Mode compression")
            return self.compress()
        else:
            # Aucun contenu traitable
            self.log("⚠️ Aucun fichier .wsquashfs ou dossier trouvé")
            return {
                "converted_games": 0,
                "error_count": 0,
                "total_files": 0,
                "stopped": False
            }

# Factory pour créer les handlers
def create_handler(handler_type: str, tools_path: str, log_callback: Callable, progress_callback: Callable):
    """Factory pour créer les handlers selon le type"""
    handlers = {
        "chd_v5": ChdV5Handler,
        "rvz": RvzHandler,
        "xbox_patch": XboxPatchHandler,
        "squashfs": SquashFSHandler
    }
    
    if handler_type not in handlers:
        raise ValueError(f"Handler type '{handler_type}' not supported")
    
    return handlers[handler_type](tools_path, log_callback, progress_callback)
