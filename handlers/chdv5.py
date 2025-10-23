from .base import ConversionHandler
from pathlib import Path

class ChdV5Handler(ConversionHandler):
    """Handler unifié ISO/CUE/GDI > CHD :
    - .cue  => createcd
    - .iso  => createdvd
    - .gdi  => createcd
    Détection automatique selon l'extension, un seul bouton dans l'UI."""

    def convert(self) -> dict:
        dest_path = Path(self.dest_folder)
        dest_path.mkdir(exist_ok=True)
        try:
            # Récupérer sources mixtes (ISO + CUE) + archives contenant ces formats
            source_files_iso = self.get_all_source_files(".iso")
            source_files_cue = self.get_all_source_files(".cue")
            source_files_gdi = self.get_all_source_files(".gdi")
            source_files = source_files_iso + source_files_cue + source_files_gdi
            self.log(f"📁 Sources détectées : {len(source_files)} (.iso / .cue / .gdi / archives)")

            converted = 0
            errors = 0

            for i, (source_item, extract_type) in enumerate(source_files):
                if self.check_should_stop():
                    break
                self.progress((i / max(1, len(source_files))) * 100, f"Traitement {i+1}/{len(source_files)}")

                # Déterminer les fichiers à traiter (direct ou après extraction)
                if extract_type is None:
                    input_files = [source_item]
                    self.log(f"📄 Fichier: {source_item.name}")
                elif extract_type == "archive":
                    self.log(f"📦 Extraction archive: {source_item.name}")
                    try:
                        extracted_folder = self.extract_single_archive(source_item)
                        # Non récursif: uniquement fichiers directement extraits au premier niveau
                        input_files = []
                        for item in extracted_folder.iterdir():
                            if item.is_file() and item.suffix.lower() in (".iso", ".cue", ".gdi"):
                                input_files.append(item)
                        self.log(f"🗂️ Trouvé {len(input_files)} fichiers exploitables dans l'archive")
                    except Exception as e:
                        self.log(f"❌ Échec extraction {source_item.name}: {e}")
                        errors += 1
                        continue
                else:
                    continue  # Type inconnu

                # Parcourir chaque fichier trouvé
                for input_file in input_files:
                    if self.check_should_stop():
                        break
                    ext = input_file.suffix.lower()
                    chd_file = dest_path / f"{input_file.stem}.chd"
                    if chd_file.exists():
                        self.log(f"⏭️ Déjà converti : {chd_file.name}")
                        continue

                    if ext == ".cue":
                        cmd = "createcd"
                    elif ext == ".iso":
                        cmd = "createdvd"
                    elif ext == ".gdi":
                        cmd = "createcd"
                    else:
                        self.log(f"⚠️ Extension ignorée: {input_file.name}")
                        continue

                    args = [
                        cmd,
                        "-i", str(input_file),
                        "-o", str(chd_file)
                    ]
                    self.log(f"🔧 chdman {cmd} → {chd_file.name}")
                    if self.run_tool("chdman.exe", args, show_output=True):
                        converted += 1
                        self.log(f"✅ OK : {input_file.name} → {chd_file.name}")
                    else:
                        errors += 1
                        self.log(f"❌ Échec : {input_file.name}")

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
