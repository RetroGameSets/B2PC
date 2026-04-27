import subprocess
import os
import shutil
import re
import tempfile
from pathlib import Path
from typing import List, Callable, Optional, Union


class ConversionHandler:
    """Classe de base pour tous les handlers de conversion"""
    def __init__(self, tools_path: Optional[str] = None, log_callback: Optional[Callable] = None, progress_callback: Optional[Callable] = None):
        # Toujours utiliser 'ressources' comme racine par défaut
        self.tools_path = Path(tools_path) if tools_path else Path("ressources")
        self.log = log_callback if log_callback else print
        self.progress = progress_callback if progress_callback else lambda p, m: None
        self.source_folder = ""
        self.dest_folder = ""
        self.temp_extract_folder = None
        self.should_stop = False  # Flag pour arrêter la conversion
        self.current_process = None  # Référence au processus en cours
    def validate_tools(self) -> bool:
        """Valide que tous les outils requis sont présents (compatibilité PyInstaller)"""
        from main import resource_path
        required_tools = [
            "7za.exe", "chdman.exe", "dolphin-tool.exe",
            "xiso.exe", "gensquashfs.exe", "unsquashfs.exe"
        ]
        for tool in required_tools:
            tool_path = resource_path(f"ressources/{tool}")
            if not os.path.exists(tool_path):
                self.log(f"❌ Outil manquant : {tool}")
                return False
        self.log("✅ Tous les outils sont présents")
        return True
    def stop_conversion(self):
        """Arrête la conversion en cours"""
        self.should_stop = True
        self.log("🛑 Arrêt de la conversion demandé...")
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
    def convert(self) -> dict:
        """Conversion par défaut: doit être surchargée par les sous-classes"""
        raise NotImplementedError("convert() non implémenté")
    def compress(self) -> dict:
        """Compression (optionnelle) - utile pour SquashFSHandler"""
        raise NotImplementedError("compress() non implémenté pour ce handler")
    def extract(self) -> dict:
        """Extraction (optionnelle) - utile pour SquashFSHandler"""
        raise NotImplementedError("extract() non implémenté pour ce handler")
    def run_tool(self, tool_name: str, args: List[str], cwd: Optional[str] = None, show_output: bool = True) -> bool:
        """Exécute un outil externe avec gestion d'erreurs.

        Pour certains outils (gensquashfs/unsquashfs) on exécute directement dans le dossier
        ressources pour conserver les DLL adjacentes.
        """
        import sys, shutil, tempfile
        if self.check_should_stop():
            return False
        from main import resource_path
        src_tool_path = resource_path(f"ressources/{tool_name}")
        if not os.path.exists(src_tool_path):
            self.log(f"❌ Outil introuvable: {tool_name}")
            return False
        special_tools = {"gensquashfs.exe", "unsquashfs.exe"}
        if tool_name in special_tools:
            temp_tool_path = src_tool_path
        else:
            temp_dir = tempfile.gettempdir()
            temp_tool_path = os.path.join(temp_dir, tool_name)
            try:
                shutil.copy2(src_tool_path, temp_tool_path)
            except Exception as e:
                self.log(f"❌ Impossible de préparer {tool_name}: {e}")
                return False
        cmd = [temp_tool_path] + args
        self.log(f"🔧 Exécution : {' '.join(cmd)}")
        flags = 0
        if sys.platform == "win32":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        saw_not_wii_disc = False
        try:
            if show_output:
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=cwd,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    creationflags=flags
                )
                if self.current_process.stdout:
                    while True:
                        if self.check_should_stop():
                            self.current_process.terminate()
                            return False
                        line = self.current_process.stdout.readline()
                        if line:
                            line = line.strip()
                            if line:
                                line_lower = line.lower()
                                if "not a wii disc" in line_lower:
                                    saw_not_wii_disc = True

                                progress_value = self._extract_progress(line, tool_name)
                                if progress_value is not None:
                                    self.progress(progress_value, f"{tool_name}: {progress_value:.1f}%")
                                elif self._is_important_message(line, tool_name) or saw_not_wii_disc:
                                    self.log(f"   {line}")
                        elif self.current_process.poll() is not None:
                            break
                self.current_process.wait()
            else:
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=cwd,
                    text=True,
                    creationflags=flags
                )
                stdout, stderr = self.current_process.communicate()
            if self.check_should_stop():
                return False
            if self.current_process.returncode == 0:
                return True
            else:
                if not show_output:
                    self.log(f"❌ Erreur {tool_name}: {stderr if 'stderr' in locals() else 'Erreur inconnue'}")
                else:
                    if tool_name == "wbfs_file.exe" and saw_not_wii_disc:
                        self.log("⚠️ Fichier ignore: ce n'est pas un ISO Wii (GameCube ou format non supporte)")
                    self.log(f"❌ {tool_name} terminé avec erreur (code: {self.current_process.returncode})")
                return False
        except Exception as e:
            self.log(f"❌ Exception lors de l'exécution de {tool_name}: {str(e)}")
            return False
        finally:
            self.current_process = None
    def _extract_progress(self, line: str, tool_name: str) -> Optional[float]:
        import re
        patterns = {
            "chdman.exe": [
                r"(\d+(?:\.\d+)?)%\s+complete",
                r"Compression:\s*(\d+(?:\.\d+)?)%",
                r"(\d+(?:\.\d+)?)%",
            ],
            "dolphin-tool.exe": [
                r"(\d+(?:\.\d+)?)%",
            ],
            "7za.exe": [
                r"(\d+(?:\.\d+)?)%",
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
        important_keywords = [
            "complete", "completed", "finished", "done", "success",
            "error", "failed", "warning", "exception",
            "final ratio", "compression ratio", "total time",
            "created", "extracted", "converted"
        ]
        tool_keywords = {
            "chdman.exe": [
                "compression complete", "final ratio", "created"
            ],
            "dolphin-tool.exe": [
                "successfully converted", "conversion complete"
            ],
            "7za.exe": [
                "everything is ok", "files", "folders"
            ],
            "wbfs_file.exe": [
                "not a wii disc", "writing:", "done in"
            ]
        }
        line_lower = line.lower()
        if re.match(r"^\s*\d+%\s*$", line):
            return False
        for keyword in important_keywords:
            if keyword in line_lower:
                return True
        if tool_name in tool_keywords:
            for keyword in tool_keywords[tool_name]:
                if keyword in line_lower:
                    return True
        return False
    def detect_archives(self, folder_path: Path) -> List[Path]:
        """Détecte seulement les archives situées au NIVEAU RACINE du dossier source (non récursif)."""
        archive_extensions = [".zip", ".rar", ".7z"]
        archives = [p for p in folder_path.iterdir() if p.is_file() and p.suffix.lower() in archive_extensions]
        if archives:
            self.log(f"📦 Détecté {len(archives)} archive(s) (niveau racine)")
            for archive in archives:
                self.log(f"   📁 {archive.name}")
        return archives
    def extract_archive(self, archive_path: Path, extract_to: Path) -> bool:
        extract_to.mkdir(exist_ok=True)
        args = [
            "x",
            str(archive_path),
            f"-o{extract_to}",
            "-y"
        ]
        self.log(f"📂 Extraction: {archive_path.name} → {extract_to.name}")
        if self.run_tool("7za.exe", args):
            self.log(f"✅ Archive extraite: {archive_path.name}")
            return True
        else:
            self.log(f"❌ Échec extraction: {archive_path.name}")
            return False
    def get_multiple_source_files(self, extensions: List[str]) -> List[tuple]:
        """Récupère tous les fichiers avec les extensions données + archives (détection unique)."""
        source_path = Path(self.source_folder)
        files_list = []
        
        # Fichiers uniquement au niveau racine
        for file_path in source_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in [ext.lower() for ext in extensions]:
                files_list.append((file_path, None))
        
        # Détecter les archives une seule fois
        archives = self.detect_archives(source_path)
        for archive in archives:
            files_list.append((archive, "archive"))
        
        return files_list

    def get_all_source_files(self, file_extension: str) -> List[tuple]:
        source_path = Path(self.source_folder)
        files_list = []
        # Fichiers uniquement au niveau racine
        for file_path in source_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() == file_extension.lower():
                files_list.append((file_path, None))
        archives = self.detect_archives(source_path)
        for archive in archives:
            files_list.append((archive, "archive"))
        return files_list

    def _create_temp_workspace(self, prefix: str) -> Path:
        """Cree un dossier temporaire, de preference sous <destination>/TEMP."""
        temp_root = None
        if self.dest_folder:
            try:
                dest_path = Path(self.dest_folder)
                dest_path.mkdir(parents=True, exist_ok=True)
                temp_root = dest_path / "TEMP"
                temp_root.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.log(f"⚠️ Impossible de preparer TEMP dans la destination: {e}")

        if temp_root:
            temp_folder = Path(tempfile.mkdtemp(prefix=prefix, dir=str(temp_root)))
        else:
            temp_folder = Path(tempfile.mkdtemp(prefix=prefix))

        self.log(f"📂 Dossier temporaire créé: {temp_folder}")
        return temp_folder

    def extract_single_archive(self, archive_path: Path) -> Path:
        if not self.temp_extract_folder:
            self.temp_extract_folder = self._create_temp_workspace("B2PC_extract_")
        archive_extract_folder = self.temp_extract_folder / f"extracted_{archive_path.stem}"
        if self.extract_archive(archive_path, archive_extract_folder):
            return archive_extract_folder
        else:
            raise Exception(f"Échec extraction de {archive_path.name}")
    def prepare_source_folder(self) -> str:
        source_path = Path(self.source_folder)
        archives = self.detect_archives(source_path)
        if not archives:
            self.log("📁 Aucune archive détectée, utilisation directe du dossier source")
            return self.source_folder
        self.temp_extract_folder = self._create_temp_workspace("B2PC_extract_")
        self.log("📋 Copie des fichiers non-archive...")
        for item in source_path.iterdir():
            if item.is_file() and item.suffix.lower() not in [".zip", ".rar", ".7z"]:
                dest_file = self.temp_extract_folder / item.name
                try:
                    shutil.copy2(item, dest_file)
                except Exception as e:
                    self.log(f"⚠️ Copie ignorée {item.name}: {e}")
        extracted_count = 0
        for archive in archives:
            archive_extract_folder = self.temp_extract_folder / f"extracted_{archive.stem}"
            if self.extract_archive(archive, archive_extract_folder):
                extracted_count += 1
        self.log(f"📊 Extraction terminée: {extracted_count}/{len(archives)} archives extraites")
        if extracted_count > 0:
            self.log(f"✅ Utilisation du dossier temporaire: {self.temp_extract_folder}")
            return str(self.temp_extract_folder)
        else:
            self.log("⚠️ Aucune extraction réussie, utilisation du dossier source original")
            return self.source_folder
    def cleanup_temp_folder(self):
        if self.temp_extract_folder and self.temp_extract_folder.exists():
            try:
                shutil.rmtree(self.temp_extract_folder)
                self.log(f"🧹 Dossier temporaire nettoyé: {self.temp_extract_folder}")
                temp_root = self.temp_extract_folder.parent
                if temp_root.name == "TEMP" and temp_root.exists() and not any(temp_root.iterdir()):
                    temp_root.rmdir()
                    self.log(f"🧹 Dossier TEMP supprimé: {temp_root}")
                                
            except Exception as e:
                self.log(f"⚠️ Erreur nettoyage dossier temporaire: {str(e)}")
            finally:
                self.temp_extract_folder = None
