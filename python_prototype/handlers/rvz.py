from .base import ConversionHandler
from pathlib import Path

class RvzHandler(ConversionHandler):
    """Handler pour conversion ISO vers RVZ (GameCube/Wii)"""
    def convert(self) -> dict:
        """Convertit les ISOs GameCube/Wii en RVZ avec extraction à la volée"""
        dest_path = Path(self.dest_folder)
        dest_path.mkdir(exist_ok=True)
        try:
            source_files = self.get_all_source_files(".iso")
            self.log(f"🎮 Traitement de {len(source_files)} sources GameCube/Wii")
            converted = 0
            errors = 0
            for i, (source_item, extract_type) in enumerate(source_files):
                if self.check_should_stop():
                    break
                self.progress((i / len(source_files)) * 100, f"Traitement RVZ {i+1}/{len(source_files)}")
                if extract_type is None:
                    iso_files = [source_item]
                    self.log(f"📄 Traitement direct: {source_item.name}")
                elif extract_type == "archive":
                    self.log(f"📦 Extraction de l'archive: {source_item.name}")
                    try:
                        extracted_folder = self.extract_single_archive(source_item)
                        iso_files = list(extracted_folder.rglob("*.iso"))
                        self.log(f"📁 Trouvé {len(iso_files)} ISOs dans l'archive")
                    except Exception as e:
                        self.log(f"❌ Échec extraction {source_item.name}: {str(e)}")
                        errors += 1
                        continue
                for iso_file in iso_files:
                    if self.check_should_stop():
                        break
                    rvz_file = dest_path / f"{iso_file.stem}.rvz"
                    if rvz_file.exists():
                        self.log(f"⏭️ RVZ déjà existant : {rvz_file.name}")
                        continue
                    args = [
                        "convert",
                        "-f", "rvz",
                        "-c", "zstd",
                        "-l", "5",
                        "-i", str(iso_file),
                        "-o", str(rvz_file)
                    ]
                    if self.run_tool("dolphin-tool.exe", args, show_output=True):
                        converted += 1
                        self.log(f"🐬 Converti en RVZ : {iso_file.name}")
                    else:
                        errors += 1
                        self.log(f"❌ Échec RVZ : {iso_file.name}")
                if self.check_should_stop():
                    break
            if self.should_stop:
                self.log("🛑 Conversion arrêtée par l'utilisateur")
            return {
                "converted_games": converted,
                "error_count": errors,
                "total_files": len(source_files),
                "stopped": self.should_stop
            }
        finally:
            self.cleanup_temp_folder()
