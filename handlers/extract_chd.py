from .base import ConversionHandler
from pathlib import Path
import subprocess
import re

class ExtractChdHandler(ConversionHandler):
    """Handler pour extraction CHD vers BIN/CUE"""
    def _detect_chd_type(self, chd_path: Path) -> str:
        """Détecte le type du CHD (CD ou DVD) via 'chdman info'.

        Retourne 'CD' ou 'DVD'. Si indéterminé, retourne 'CD' par défaut.
        Heuristiques :
          - Présence de Tag='DVD dans une ligne Metadata
          - Présence de TRACK:1 => CD
          - Taille logique (> ~1.5GB) => DVD
        """
        chdman = self.tools_path / 'chdman.exe' if hasattr(self, 'tools_path') else Path('ressources/chdman.exe')
        try:
            proc = subprocess.run([str(chdman), 'info', '--input', str(chd_path)], capture_output=True, text=True, timeout=30)
            output = (proc.stdout + '\n' + proc.stderr).splitlines()
        except Exception as e:
            self.log(f"⚠️ Impossible de lire infos CHD ({chd_path.name}) : {e}")
            return 'CD'

        logical_size = None
        is_dvd = False
        for line in output:
            line = line.strip()
            if "Tag='DVD" in line:
                is_dvd = True
            if 'TRACK:1' in line:
                # Indique généralement un CD, on note mais on continue pour détecter un tag DVD éventuel
                pass
            if line.startswith('Logical size:'):
                # Extraire nombre d'octets
                digits = re.sub(r'[^0-9]', '', line.split(':', 1)[1])
                if digits:
                    try:
                        logical_size = int(digits)
                    except Exception:
                        logical_size = None
        if not is_dvd and logical_size is not None:
            # Seuil 1.5 Go
            if logical_size > 1_500 * 1024 * 1024:
                is_dvd = True
        return 'DVD' if is_dvd else 'CD'

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
                    chd_files = [p for p in extracted_folder.iterdir() if p.is_file() and p.suffix.lower()==".chd"]
                    self.log(f"📁 Trouvé {len(chd_files)} CHD dans l'archive")
                except Exception as e:
                    self.log(f"❌ Échec extraction {source_item.name}: {str(e)}")
                    errors += 1
                    continue
            for chd_file in chd_files:
                if self.check_should_stop():
                    break
                base_name = chd_file.stem
                chd_type = self._detect_chd_type(chd_file)
                if chd_type == 'DVD':
                    iso_file = dest_path / f"{base_name}.iso"
                    if iso_file.exists():
                        self.log(f"⏭️ Déjà extrait (DVD) : {iso_file.name}")
                        continue
                    self.log(f"🔍 Type détecté DVD pour {chd_file.name}")
                    args = [
                        "extractdvd",
                        "-i", str(chd_file),
                        "-o", str(iso_file)
                    ]
                    if self.run_tool("chdman.exe", args, show_output=True):
                        extracted += 1
                        self.log(f"✅ Extrait : {chd_file.name} → {iso_file.name}")
                    else:
                        errors += 1
                        self.log(f"❌ Échec extraction DVD : {chd_file.name}")
                else:
                    cue_file = dest_path / f"{base_name}.cue"
                    bin_file = dest_path / f"{base_name}.bin"
                    if bin_file.exists() and cue_file.exists():
                        self.log(f"⏭️ Déjà extrait (CD) : {bin_file.name} / {cue_file.name}")
                        continue
                    self.log(f"🔍 Type détecté CD pour {chd_file.name}")
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
                        self.log(f"❌ Échec extraction CD : {chd_file.name}")
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
