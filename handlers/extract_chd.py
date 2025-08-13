from .base import ConversionHandler
from pathlib import Path

class ExtractChdHandler(ConversionHandler):
    """Handler pour extraction CHD vers BIN/CUE"""
    def convert(self) -> dict:
        """Extrait les fichiers CHD en BIN/CUE avec chdman.exe"""
        dest_path = Path(self.dest_folder)
        dest_path.mkdir(exist_ok=True)
        source_files = self.get_all_source_files(".chd")
        self.log(f"📁 Trouvé {len(source_files)} CHD à extraire")
        extracted = 0
        errors = 0
        for i, (source_item, extract_type) in enumerate(source_files):
            if self.check_should_stop():
                break
            self.progress((i / len(source_files)) * 100, f"Traitement {i+1}/{len(source_files)}")
            if extract_type is None:
                chd_files = [source_item]
                self.log(f"📄 Traitement direct: {source_item.name}")
            elif extract_type == "archive":
                self.log(f"📦 Extraction de l'archive: {source_item.name}")
                try:
                    extracted_folder = self.extract_single_archive(source_item)
                    chd_files = list(extracted_folder.rglob("*.chd"))
                    self.log(f"📁 Trouvé {len(chd_files)} CHD dans l'archive")
                except Exception as e:
                    self.log(f"❌ Échec extraction {source_item.name}: {str(e)}")
                    errors += 1
                    continue
            for chd_file in chd_files:
                if self.check_should_stop():
                    break
                base_name = chd_file.stem
                cue_file = dest_path / f"{base_name}.cue"
                bin_file = dest_path / f"{base_name}.bin"
                if bin_file.exists() and cue_file.exists():
                    self.log(f"⏭️ Déjà extrait : {bin_file.name} / {cue_file.name}")
                    continue
                args = [
                    "extractcd",
                    "-i", str(chd_file),
                    "-o", str(cue_file)
                ]
                if self.run_tool("chdman.exe", args, show_output=True):
                    extracted += 1
                    self.log(f"✅ Extrait : {chd_file.name} → {bin_file.name} / {cue_file.name}")
                else:
                    errors += 1
                    self.log(f"❌ Échec extraction : {chd_file.name}")
            if self.check_should_stop():
                break
        if self.should_stop:
            self.log("🛑 Extraction arrêtée par l'utilisateur")
        return {
            "extracted_games": extracted,
            "error_count": errors,
            "total_files": len(source_files),
            "stopped": self.should_stop
        }
    # Pas de cleanup_temp() nécessaire ici
