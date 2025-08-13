from .base import ConversionHandler
from .chdv5 import ChdV5Handler
from .extract_chd import ExtractChdHandler
from pathlib import Path

class MergeBinCueHandler(ConversionHandler):
    """Handler pour fusionner BIN/CUE en un nouveau BIN/CUE propre via CHD roundtrip"""
    def convert(self) -> dict:
        """Convertit BIN/CUE en CHD puis extrait en BIN/CUE (roundtrip)"""
        dest_path = Path(self.dest_folder)
        dest_path.mkdir(exist_ok=True)
        # 1. Conversion en CHD
        chd_temp = dest_path / "_temp_chd"
        chd_temp.mkdir(exist_ok=True)
        chd_handler = ChdV5Handler(str(self.tools_path), self.log, self.progress)
        chd_handler.source_folder = self.source_folder
        chd_handler.dest_folder = str(chd_temp)
        chd_handler.should_stop = self.should_stop
        chd_result = chd_handler.convert()
        if chd_result.get("error_count", 0) > 0 or chd_handler.should_stop:
            self.log("❌ Erreur lors de la conversion en CHD, fusion annulée")
            return {"error": "Erreur conversion CHD", **chd_result}
        # 2. Extraction du CHD en BIN/CUE
        extract_handler = ExtractChdHandler(str(self.tools_path), self.log, self.progress)
        extract_handler.source_folder = str(chd_temp)
        extract_handler.dest_folder = self.dest_folder
        extract_handler.should_stop = self.should_stop
        extract_result = extract_handler.convert()
        # Nettoyage du dossier temporaire
        for f in chd_temp.glob("*.chd"):
            try:
                f.unlink()
            except Exception:
                pass
        try:
            chd_temp.rmdir()
        except Exception:
            pass
        # Fusion des résultats
        return {
            "merged_games": extract_result.get("extracted_games", 0),
            "error_count": extract_result.get("error_count", 0),
            "stopped": extract_handler.should_stop or chd_handler.should_stop
        }
