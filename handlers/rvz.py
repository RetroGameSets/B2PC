from .base import ConversionHandler
from pathlib import Path


class RvzHandler(ConversionHandler):
    """Handler pour conversion bidirectionnelle ISO <-> RVZ (GameCube/Wii)."""

    def __init__(self, tools_path=None, log_callback=None, progress_callback=None):
        super().__init__(tools_path, log_callback, progress_callback)
        # Valeurs: iso_to_rvz | rvz_to_iso
        self.direction = "iso_to_rvz"

    def _source_extension(self) -> str:
        if self.direction == "rvz_to_iso":
            return ".rvz"
        return ".iso"

    def _archive_files(self, extracted_folder: Path):
        wanted_ext = self._source_extension()
        return [p for p in extracted_folder.iterdir() if p.is_file() and p.suffix.lower() == wanted_ext]

    def _convert_file(self, source_file: Path, dest_path: Path) -> bool:
        if self.direction == "rvz_to_iso":
            output_file = dest_path / f"{source_file.stem}.iso"
            if output_file.exists():
                self.log(f"⏭️ ISO deja existant : {output_file.name}")
                return True

            args = [
                "convert",
                "-f", "iso",
                "-i", str(source_file),
                "-o", str(output_file)
            ]
            if self.run_tool("dolphin-tool.exe", args, show_output=True):
                self.log(f"🐬 Converti en ISO : {source_file.name}")
                return True

            self.log(f"❌ Échec ISO : {source_file.name}")
            return False

        output_file = dest_path / f"{source_file.stem}.rvz"
        if output_file.exists():
            self.log(f"⏭️ RVZ déjà existant : {output_file.name}")
            return True

        args = [
            "convert",
            "-f", "rvz",
            "-c", "zstd",
            "-l", "5",
            "-b", "131072",
            "-i", str(source_file),
            "-o", str(output_file)
        ]
        if self.run_tool("dolphin-tool.exe", args, show_output=True):
            self.log(f"🐬 Converti en RVZ : {source_file.name}")
            return True

        self.log(f"❌ Échec RVZ : {source_file.name}")
        return False

    def convert(self) -> dict:
        """Convertit ISO->RVZ ou RVZ->ISO avec extraction d'archives."""
        dest_path = Path(self.dest_folder)
        dest_path.mkdir(exist_ok=True)
        try:
            source_ext = self._source_extension()
            source_files = self.get_all_source_files(source_ext)

            if self.direction == "rvz_to_iso":
                self.log(f"🎮 Traitement de {len(source_files)} source(s) RVZ")
                progress_label = "Traitement [GC/WII] RVZ > ISO"
            else:
                self.log(f"🎮 Traitement de {len(source_files)} source(s) ISO")
                progress_label = "Traitement ISO > RVZ"

            converted = 0
            errors = 0
            total_sources = max(1, len(source_files))

            for i, (source_item, extract_type) in enumerate(source_files):
                if self.check_should_stop():
                    break

                self.progress((i / total_sources) * 100, f"{progress_label} {i+1}/{len(source_files)}")

                if extract_type is None:
                    input_files = [source_item]
                    self.log(f"📄 Traitement direct: {source_item.name}")
                elif extract_type == "archive":
                    self.log(f"📦 Extraction de l'archive: {source_item.name}")
                    try:
                        extracted_folder = self.extract_single_archive(source_item)
                        input_files = self._archive_files(extracted_folder)
                        if self.direction == "rvz_to_iso":
                            self.log(f"📁 Trouvé {len(input_files)} RVZ dans l'archive")
                        else:
                            self.log(f"📁 Trouvé {len(input_files)} ISOs dans l'archive")
                    except Exception as e:
                        self.log(f"❌ Échec extraction {source_item.name}: {str(e)}")
                        errors += 1
                        continue

                for input_file in input_files:
                    if self.check_should_stop():
                        break

                    if self._convert_file(input_file, dest_path):
                        converted += 1
                        if extract_type is None:
                            self.delete_source_after_success(input_file)
                    else:
                        errors += 1

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
