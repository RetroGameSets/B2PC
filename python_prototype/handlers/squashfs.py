from .base import ConversionHandler
from pathlib import Path

class SquashFSHandler(ConversionHandler):
    """Handler pour compression/décompression wSquashFS"""
    def get_all_source_files(self, source_path: str = "") -> list:
        if not source_path:
            source_path = self.source_folder
        source_dir = Path(source_path)
        source_files = []
        for item in source_dir.iterdir():
            if item.is_dir():
                source_files.append(str(item))
        return source_files
    def compress(self) -> dict:
        dest_path = Path(self.dest_folder)
        dest_path.mkdir(exist_ok=True)
        try:
            source_path = Path(self.source_folder)
            archives = self.detect_archives(source_path)
            items_to_compress = []
            for item in source_path.iterdir():
                if item.is_dir():
                    items_to_compress.append((item, None, "folder"))
                    self.log(f"📁 Dossier trouvé: {item.name}")
            for archive in archives:
                items_to_compress.append((archive, "archive", "archive"))
                self.log(f"📦 Archive trouvée: {archive.name}")
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
                    squashfs_file = dest_path / f"{source_item.name}.wsquashfs"
                    if self._compress_folder(source_item, squashfs_file):
                        compressed += 1
                    else:
                        errors += 1
                elif item_type == "archive":
                    self.log(f"📦 Extraction puis compression de l'archive: {source_item.name}")
                    try:
                        extracted_folder = self.extract_single_archive(source_item)
                        for extracted_item in extracted_folder.iterdir():
                            if extracted_item.is_dir():
                                squashfs_file = dest_path / f"{extracted_item.name}.wsquashfs"
                                if self._compress_folder(extracted_item, squashfs_file):
                                    compressed += 1
                                else:
                                    errors += 1
                    except Exception as e:
                        self.log(f"❌ Échec extraction archive {source_item.name}: {str(e)}")
                        errors += 1
                        continue
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
        dest_path = Path(self.dest_folder)
        dest_path.mkdir(exist_ok=True)
        try:
            source_files = self.get_all_source_files_extract(".wsquashfs")
            self.log(f"📂 Traitement de {len(source_files)} sources SquashFS")
            extracted = 0
            errors = 0
            for i, (source_item, extract_type) in enumerate(source_files):
                if self.check_should_stop():
                    break
                if isinstance(source_item, str):
                    source_item = Path(source_item)
                self.progress((i / len(source_files)) * 100, f"Extraction {i+1}/{len(source_files)}")
                if extract_type is None:
                    squashfs_files = [source_item]
                    self.log(f"📄 Extraction directe: {source_item.name}")
                elif extract_type == "archive":
                    self.log(f"📦 Extraction de l'archive: {source_item.name}")
                    try:
                        extracted_folder = self.extract_single_archive(source_item)
                        squashfs_files = list(extracted_folder.rglob("*.wsquashfs"))
                        self.log(f"📁 Trouvé {len(squashfs_files)} fichiers SquashFS dans l'archive")
                    except Exception as e:
                        self.log(f"❌ Échec extraction archive {source_item.name}: {str(e)}")
                        errors += 1
                        continue
                for squashfs_file in squashfs_files:
                    if self.check_should_stop():
                        break
                    if isinstance(squashfs_file, str):
                        squashfs_file = Path(squashfs_file)
                    extract_dir = dest_path / squashfs_file.stem
                    if extract_dir.exists():
                        self.log(f"⏭️ Dossier déjà extrait : {extract_dir.name}")
                        continue
                    args = [
                        "--unpack-path", "/",
                        "--unpack-root", str(extract_dir),
                        str(squashfs_file)
                    ]
                    self.log(f"🔧 Commande: unsquashfs.exe {' '.join(args)}")
                    if self.run_tool("unsquashfs.exe", args):
                        extracted += 1
                        self.log(f"📂 Extrait : {squashfs_file.name} → {extract_dir.name}")
                    else:
                        errors += 1
                        self.log(f"❌ Échec extraction : {squashfs_file.name}")
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
    def get_all_source_files_extract(self, file_extension: str) -> list:
        source_path = Path(self.source_folder)
        files_list = []
        direct_files = list(source_path.rglob(f"*{file_extension}"))
        for file_path in direct_files:
            files_list.append((str(file_path), None))
        archives = self.detect_archives(source_path)
        for archive in archives:
            files_list.append((str(archive), "archive"))
        return files_list
    def convert(self) -> dict:
        source_path = Path(self.source_folder)
        wsquashfs_files = list(source_path.rglob("*.wsquashfs"))
        directories = [item for item in source_path.iterdir() if item.is_dir()]
        if wsquashfs_files:
            self.log("🔍 Fichiers .wsquashfs détectés → Mode extraction")
            return self.extract()
        elif directories:
            self.log("📁 Dossiers détectés → Mode compression")
            return self.compress()
        else:
            self.log("⚠️ Aucun fichier .wsquashfs ou dossier trouvé")
            return {
                "converted_games": 0,
                "error_count": 0,
                "total_files": 0,
                "stopped": False
            }
