from .base import ConversionHandler
from pathlib import Path
import shutil

class XboxPatchHandler(ConversionHandler):
    """Handler pour patch des ISOs Xbox"""
    def convert(self) -> dict:
        """Patch les ISOs Xbox avec xiso - extraction à la volée"""
        dest_path = Path(self.dest_folder)
        dest_path.mkdir(exist_ok=True)
        try:
            source_files = self.get_all_source_files(".iso")
            self.log(f"🎮 Traitement de {len(source_files)} sources Xbox")
            patched = 0
            errors = 0
            for i, (source_item, extract_type) in enumerate(source_files):
                if self.check_should_stop():
                    break
                self.progress((i / len(source_files)) * 100, f"Traitement Xbox {i+1}/{len(source_files)}")
                if extract_type is None:
                    iso_files = [source_item]
                    self.log(f"📄 Traitement direct: {source_item.name}")
                elif extract_type == "archive":
                    self.log(f"📦 Extraction de l'archive: {source_item.name}")
                    try:
                        extracted_folder = self.extract_single_archive(source_item)
                        iso_files = [p for p in extracted_folder.iterdir() if p.is_file() and p.suffix.lower()==".iso"]
                        self.log(f"📁 Trouvé {len(iso_files)} ISOs dans l'archive")
                    except Exception as e:
                        self.log(f"❌ Échec extraction {source_item.name}: {str(e)}")
                        errors += 1
                        continue
                for iso_file in iso_files:
                    if self.check_should_stop():
                        break
                    dest_iso = dest_path / iso_file.name
                    shutil.copy2(iso_file, dest_iso)
                    args = ["-r", str(dest_iso)]
                    if self.run_tool("xiso.exe", args, cwd=str(dest_path)):
                        patched += 1
                        self.log(f"🔧 ISO Xbox patché : {iso_file.name}")
                        self._cleanup_xbox_temp_files(dest_path, iso_file.name)
                    else:
                        errors += 1
                        self.log(f"❌ Échec patch Xbox : {iso_file.name}")
                        self._cleanup_xbox_temp_files(dest_path, iso_file.name)
                if self.check_should_stop():
                    break
            if self.should_stop:
                self.log("🛑 Conversion arrêtée par l'utilisateur")
            return {
                "converted_games": patched,
                "error_count": errors,
                "total_files": len(source_files),
                "stopped": self.should_stop
            }
        finally:
            self.cleanup_temp_folder()
    def _cleanup_xbox_temp_files(self, dest_path: Path, iso_filename: str):
        temp_patterns = [
            f"{iso_filename}.old",
            f"{iso_filename}.bak",
            f"{iso_filename}.tmp",
            f"~{iso_filename}",
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
        try:
            for temp_file in dest_path.glob(f"{Path(iso_filename).stem}.*"):
                if temp_file.suffix.lower() in ['.tmp', '.temp', '.backup', '.bk']:
                    try:
                        temp_file.unlink()
                        cleaned_files.append(temp_file.name)
                        self.log(f"🧹 Fichier temporaire supprimé : {temp_file.name}")
                    except Exception as e:
                        self.log(f"⚠️ Impossible de supprimer {temp_file.name}: {str(e)}")
        except Exception:
            pass
        if cleaned_files:
            self.log(f"✅ Nettoyage terminé: {len(cleaned_files)} fichier(s) temporaire(s) supprimé(s)")
        else:
            self.log("ℹ️ Aucun fichier temporaire à nettoyer")
