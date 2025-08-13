from .base import ConversionHandler
from pathlib import Path

class ChdV5Handler(ConversionHandler):
    """Handler pour conversion vers CHD v5"""
    def convert(self) -> dict:
        """Convertit les ISOs en CHD v5 avec extraction à la volée"""
        dest_path = Path(self.dest_folder)
        dest_path.mkdir(exist_ok=True)
        try:
            # Prendre en compte les .iso et .cue comme sources
            source_files_iso = self.get_all_source_files(".iso")
            source_files_cue = self.get_all_source_files(".cue")
            source_files = source_files_iso + source_files_cue
            self.log(f"📁 Trouvé {len(source_files)} sources à traiter (.iso / .cue)")
            converted = 0
            errors = 0
            for i, (source_item, extract_type) in enumerate(source_files):
                if self.check_should_stop():
                    break
                self.progress((i / len(source_files)) * 100, f"Traitement {i+1}/{len(source_files)}")
                if extract_type is None:
                    input_files = [source_item]
                    self.log(f"📄 Traitement direct: {source_item.name}")
                elif extract_type == "archive":
                    self.log(f"📦 Extraction de l'archive: {source_item.name}")
                    try:
                        extracted_folder = self.extract_single_archive(source_item)
                        input_files = list(extracted_folder.rglob("*.iso")) + list(extracted_folder.rglob("*.cue"))
                        self.log(f"📁 Trouvé {len(input_files)} ISOs/CUEs dans l'archive")
                    except Exception as e:
                        self.log(f"❌ Échec extraction {source_item.name}: {str(e)}")
                        errors += 1
                        continue
                for input_file in input_files:
                    if self.check_should_stop():
                        break
                    chd_file = dest_path / f"{input_file.stem}.chd"
                    if chd_file.exists():
                        self.log(f"⏭️ Fichier déjà converti : {chd_file.name}")
                        continue
                    args = [
                        "createcd",
                        "-i", str(input_file),
                        "-o", str(chd_file)
                    ]
                    if self.run_tool("chdman.exe", args, show_output=True):
                        converted += 1
                        self.log(f"✅ Converti : {input_file.name} → {chd_file.name}")
                    else:
                        errors += 1
                        self.log(f"❌ Échec conversion : {input_file.name}")
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
