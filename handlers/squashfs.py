from .base import ConversionHandler
from pathlib import Path
import re
import shutil
import subprocess
import sys

class SquashFSHandler(ConversionHandler):
    """Handler pour compression/wSquashFS Extraction"""

    def _is_supported_wsquashfs_folder(self, folder: Path) -> bool:
        name = folder.name.lower()
        return name.endswith(".pc") or name.endswith(".ps3")

    def _get_output_extension_for_folder(self, folder: Path) -> str:
        if folder.name.lower().endswith(".ps3"):
            return ".squashfs"
        return ".wsquashfs"

    def get_all_source_files(self, source_path: str = "") -> list:
        if not source_path:
            source_path = self.source_folder
        source_dir = Path(source_path)
        source_files = []
        for item in source_dir.iterdir():
            if item.is_dir() and self._is_supported_wsquashfs_folder(item):
                source_files.append(str(item))
        return self.filter_selected_sources(source_files)

    def compress(self) -> dict:
        dest_path = Path(self.dest_folder)
        dest_path.mkdir(exist_ok=True)
        try:
            source_path = Path(self.source_folder)
            items_to_compress = []
            for item in source_path.iterdir():
                if item.is_dir():
                    if self._is_supported_wsquashfs_folder(item):
                        items_to_compress.append((item, None, "folder"))
                        self.log(f"📁 Dossier trouvé: {item.name}")
                    else:
                        self.log(f"⏭️ Dossier ignoré (suffixe non supporté): {item.name}")
                elif item.is_file() and item.suffix.lower() in {".zip", ".rar", ".7z"}:
                    self.log(f"⏭️ Archive ignorée en wSquashFS Compression: {item.name}")
            items_to_compress = self.filter_selected_sources(items_to_compress)

            if not items_to_compress:
                self.log("⚠️ Aucun dossier .pc/.ps3 trouvé pour la compression")
                return {
                    "converted_games": 0,
                    "error_count": 0,
                    "total_files": 0,
                    "stopped": self.should_stop
                }

            self.log(f"📦 Compression de {len(items_to_compress)} éléments")
            compressed = 0
            errors = 0
            for i, (source_item, extract_type, item_type) in enumerate(items_to_compress):
                if self.check_should_stop():
                    break
                if isinstance(source_item, str):
                    source_item = Path(source_item)
                self.progress((i / len(items_to_compress)) * 100, f"Compression {i+1}/{len(items_to_compress)}")
                if item_type == "folder":
                    self.log(f"📁 Compression dossier: {source_item.name}")
                    output_ext = self._get_output_extension_for_folder(source_item)
                    squashfs_file = dest_path / f"{source_item.name}{output_ext}"
                    if self._compress_folder(source_item, squashfs_file):
                        compressed += 1
                    else:
                        errors += 1
            if self.should_stop:
                self.log("🛑 Compression arrêtée par l'utilisateur")
            return {
                "converted_games": compressed,
                "error_count": errors,
                "total_files": len(items_to_compress),
                "stopped": self.should_stop
            }
        finally:
            self.cleanup_temp_folder()
    def _compress_folder(self, folder_path: Path, output_file: Path) -> bool:
        if output_file.exists():
            self.log(f"⏭️ Archive déjà existante : {output_file.name}")
            return True
        if self.check_should_stop():
            return False
        self.log(f"📦 Compression du dossier: {folder_path.name}")
        # IMPORTANT: pour gensquashfs, le fichier de sortie DOIT être le DERNIER argument
        args = [
            "--pack-dir", str(folder_path),
            "--compressor", "zstd",
            "--block-size", "1048576",
            "--num-jobs", "8",
            "--force",  # écrase si existe
            str(output_file)
        ]
        self.log(f"🔧 Commande: gensquashfs.exe {' '.join(args)}")
        if self.run_tool("gensquashfs.exe", args):
            self.log(f"✅ Compressé : {folder_path.name} → {output_file.name}")
            return True
        else:
            self.log(f"❌ Échec compression : {folder_path.name}")
            return False

    def _get_7z_executable(self) -> Path:
        from main import resource_path

        for tool_name in ("7z.exe", "7za.exe"):
            tool_path = Path(resource_path(f"ressources/{tool_name}"))
            if tool_path.exists():
                return tool_path
        raise FileNotFoundError("7z.exe/7za.exe introuvable dans ressources")

    def _run_7z(self, executable: Path, args: list, progress_label: str = "", capture_output: bool = True) -> tuple:
        if self.check_should_stop():
            return False, ""

        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        process = subprocess.Popen(
            [str(executable), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            creationflags=flags,
        )
        self.current_process = process
        try:
            output_lines = []
            recent_output_lines = []
            line_buffer = []
            last_logged_progress = -10

            def process_line(raw_line: str):
                nonlocal last_logged_progress
                line = raw_line.strip()
                if not line:
                    return
                if capture_output:
                    output_lines.append(line)
                else:
                    recent_output_lines.append(line)
                    if len(recent_output_lines) > 8:
                        recent_output_lines.pop(0)

                progress_match = re.search(r"(\d+(?:\.\d+)?)%", line)
                if progress_label and progress_match:
                    progress_value = float(progress_match.group(1))
                    self.progress(progress_value, f"{progress_label} : {progress_value:.0f}%")
                    if progress_value >= last_logged_progress + 10 or progress_value == 100:
                        self.log(f"⏳ {progress_label} : {progress_value:.0f}%")
                        last_logged_progress = progress_value

            if process.stdout:
                while True:
                    character = process.stdout.read(1)
                    if not character:
                        break
                    if self.should_stop:
                        process.terminate()
                        break
                    if character in "\r\n":
                        process_line("".join(line_buffer))
                        line_buffer.clear()
                    else:
                        line_buffer.append(character)
                process_line("".join(line_buffer))

            process.wait()
            output = "\n".join(output_lines if capture_output else recent_output_lines)
            if process.returncode != 0 and not self.should_stop:
                self.log(f"❌ 7-Zip terminé avec erreur (code : {process.returncode})")
            return process.returncode == 0 and not self.should_stop, output
        finally:
            self.current_process = None

    def _get_symbolic_link_paths(self, listing: str, game_name: str = "") -> list:
        records = []
        current_record = {}
        for line in listing.splitlines():
            if line.startswith("Path = "):
                if current_record:
                    records.append(current_record)
                current_record = {"Path": line.split(" = ", 1)[1]}
            elif " = " in line:
                key, value = line.split(" = ", 1)
                current_record[key] = value
        if current_record:
            records.append(current_record)

        game_path = f"drive_c\\{game_name}".casefold() if game_name else ""
        symbolic_links = []
        for record in records:
            path = record.get("Path", "")
            normalized_path = path.replace("/", "\\").casefold()
            mode = record.get("Mode", "").strip().lower()
            if game_path and normalized_path != game_path and not normalized_path.startswith(game_path + "\\"):
                continue
            symbolic_target = record.get("Symbolic Link", "").strip()
            is_symbolic_link = bool(symbolic_target) or (mode.startswith("l") and "Symbolic Link" not in record)
            if is_symbolic_link:
                symbolic_links.append(path)
        return symbolic_links

    def _extract_squashfs_game(self, squashfs_file: Path, dest_path: Path, index: int, extract_all: bool = False):
        ignore_games = {"program files", "program files (x86)", "programdata", "users", "windows"}
        extract_dir = None
        temp_dir = None

        try:
            seven_zip = self._get_7z_executable()
            self.log(f"🔎 Analyse de {squashfs_file.name} avec 7-Zip...")
            listed, listing = self._run_7z(seven_zip, ["l", "-slt", str(squashfs_file)])
            if not listed:
                self.log(f"❌ Impossible de lire {squashfs_file.name} avec 7-Zip")
                return False

            game_name = None
            if not extract_all:
                game_name = next(
                    (
                        match.group(1)
                        for line in listing.splitlines()
                        if (match := re.match(r"^Path = drive_c\\([^\\]+)$", line))
                        and match.group(1).lower() not in ignore_games
                    ),
                    None,
                )
                if not game_name:
                    self.log(f"❌ Aucun dossier de jeu trouvé dans {squashfs_file.name}")
                    return False

            symbolic_links = self._get_symbolic_link_paths(listing, game_name or "")
            extract_dir = dest_path / squashfs_file.stem
            if extract_all:
                self.log(f"📦 Extraction complète → dossier de sortie : {extract_dir.name}")
            else:
                self.log(f"🎮 Jeu détecté : {game_name} → dossier de sortie : {extract_dir.name}")
            if symbolic_links:
                self.log(f"🔗 {len(symbolic_links)} lien(s) symbolique(s) seront ignorés")
            if extract_dir.exists():
                self.log(f"⏭️ Dossier déjà extrait : {extract_dir.name}")
                return None

            if not self.temp_extract_folder:
                self.temp_extract_folder = self._create_temp_workspace("B2PC_extract_")
            temp_dir = self.temp_extract_folder / f"squashfs_{index}_{squashfs_file.stem}"
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            temp_dir.mkdir(parents=True)

            extraction_label = "complète" if extract_all else str(game_name)
            self.log(f"📥 Extraction en cours : {extraction_label}")
            extraction_args = ["x", str(squashfs_file)]
            if not extract_all:
                extraction_args.append(f"drive_c\\{game_name}\\*")
            extraction_args.extend(f"-x!{link_path}" for link_path in symbolic_links)
            extraction_args.extend([f"-o{temp_dir}", "-y"])
            extracted, extraction_output = self._run_7z(
                seven_zip,
                extraction_args,
                progress_label=f"Extraction {extraction_label}",
                capture_output=False,
            )
            if not extracted:
                for output_line in extraction_output.splitlines():
                    self.log(f"❌ Détail 7-Zip : {output_line}")
                self.log(f"❌ Échec extraction : {squashfs_file.name}")
                return False

            extracted_game_dir = temp_dir if extract_all else temp_dir / "drive_c" / str(game_name)
            if not extracted_game_dir.is_dir():
                self.log(f"❌ Dossier extrait introuvable : {extracted_game_dir}")
                return False

            shutil.copytree(extracted_game_dir, extract_dir)
            self.log(f"📂 Extrait : {squashfs_file.name} → {extract_dir.name}")
            return True
        except Exception as e:
            self.log(f"❌ Échec extraction {squashfs_file.name}: {e}")
            if extract_dir and extract_dir.exists():
                shutil.rmtree(extract_dir, ignore_errors=True)
            return False
        finally:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def extract(self, extract_all: bool = False) -> dict:
        dest_path = Path(self.dest_folder)
        dest_path.mkdir(exist_ok=True)
        try:
            source_files = self.get_all_source_files_extract([".wsquashfs", ".squashfs"])
            self.log(f"📂 Traitement de {len(source_files)} sources SquashFS")
            extracted = 0
            errors = 0
            for i, (source_item, extract_type) in enumerate(source_files):
                if self.check_should_stop():
                    break
                if isinstance(source_item, str):
                    source_item = Path(source_item)
                self.progress((i / len(source_files)) * 100, f"Extraction {i+1}/{len(source_files)}")
                squashfs_files = [source_item]
                self.log(f"📄 Extraction directe: {source_item.name}")
                for squashfs_file in squashfs_files:
                    if self.check_should_stop():
                        break
                    if isinstance(squashfs_file, str):
                        squashfs_file = Path(squashfs_file)
                    result = self._extract_squashfs_game(squashfs_file, dest_path, i, extract_all)
                    if result is True:
                        extracted += 1
                        self.delete_source_after_success(squashfs_file)
                    elif result is False:
                        errors += 1
                if self.check_should_stop():
                    break
            if self.should_stop:
                self.log("🛑 Extraction arrêtée par l'utilisateur")
            return {
                "converted_games": extracted,
                "error_count": errors,
                "total_files": len(source_files),
                "stopped": self.should_stop
            }
        finally:
            self.cleanup_temp_folder()
    def get_all_source_files_extract(self, file_extensions: list) -> list:
        source_path = Path(self.source_folder)
        files_list = []
        normalized_extensions = {ext.lower() for ext in file_extensions}
        direct_files = [
            p for p in source_path.iterdir()
            if p.is_file() and p.suffix.lower() in normalized_extensions
        ]
        for file_path in direct_files:
            files_list.append((str(file_path), None))
        return self.filter_selected_sources(files_list)
    def convert(self) -> dict:
        source_path = Path(self.source_folder)
        squashfs_files = [
            p for p in source_path.iterdir()
            if p.is_file() and p.suffix.lower() in {".wsquashfs", ".squashfs"}
        ]
        directories = [item for item in source_path.iterdir() if item.is_dir() and self._is_supported_wsquashfs_folder(item)]
        if squashfs_files:
            self.log("🔍 Fichiers .wsquashfs/.squashfs détectés → Mode extraction")
            return self.extract()
        elif directories:
            self.log("📁 Dossiers .pc/.ps3 détectés → Mode compression")
            return self.compress()
        else:
            self.log("⚠️ Aucun fichier .wsquashfs/.squashfs ni dossier .pc/.ps3 trouvé")
            return {
                "converted_games": 0,
                "error_count": 0,
                "total_files": 0,
                "stopped": False
            }
