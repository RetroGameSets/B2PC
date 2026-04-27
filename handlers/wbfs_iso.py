from pathlib import Path
from typing import Dict, List, Optional, Tuple
import shutil
import tempfile

from .base import ConversionHandler


class WbfsIsoHandler(ConversionHandler):
    """Handler for WBFS <-> ISO conversion using wbfs_file.exe."""

    SUPPORTED_EXTENSIONS = (".iso", ".wbfs")
    ARCHIVE_EXTENSIONS = (".zip", ".rar", ".7z")

    def __init__(self, tools_path=None, log_callback=None, progress_callback=None):
        super().__init__(tools_path, log_callback, progress_callback)
        # Allowed values: both, iso_to_wbfs, wbfs_to_iso
        self.direction = "both"

    def validate_tools(self) -> bool:
        """Validate tools needed for WBFS/ISO conversion."""
        from main import resource_path

        wbfs_tool = Path(resource_path("ressources/wbfs_file.exe"))
        if not wbfs_tool.exists():
            self.log("❌ Outil manquant : wbfs_file.exe")
            return False

        if self.direction == "wbfs_to_rvz":
            dolphin_tool = Path(resource_path("ressources/dolphin-tool.exe"))
            if not dolphin_tool.exists():
                self.log("❌ Outil manquant : dolphin-tool.exe")
                return False

        self.log("✅ Outils WBFS detectes")
        return True

    def _list_convertible_files(self, folder: Path) -> List[Path]:
        allowed = self._allowed_extensions()
        result: List[Path] = []
        seen = set()

        def add_if_match(path: Path):
            if not path.is_file() or path.suffix.lower() not in allowed:
                return
            key = str(path.resolve()).lower()
            if key in seen:
                return
            seen.add(key)
            result.append(path)

        # Niveau racine
        for p in folder.iterdir():
            add_if_match(p)

        # Recursif d'un niveau (racine/sous-dossier/fichier)
        for child in folder.iterdir():
            if not child.is_dir():
                continue
            for p in child.iterdir():
                add_if_match(p)

        return sorted(result)

    def _collect_source_items(self) -> List[Tuple[Path, Optional[str]]]:
        source_path = Path(self.source_folder)
        if not source_path.exists() or not source_path.is_dir():
            return []

        allowed_ext = set(self._allowed_extensions())
        archive_ext = set(self.ARCHIVE_EXTENSIONS)

        items: List[Tuple[Path, Optional[str]]] = []
        seen = set()

        def add_item(path: Path, extract_type: Optional[str]):
            key = (str(path.resolve()).lower(), extract_type)
            if key in seen:
                return
            seen.add(key)
            items.append((path, extract_type))

        # Niveau racine
        for entry in source_path.iterdir():
            if not entry.is_file():
                continue
            ext = entry.suffix.lower()
            if ext in allowed_ext:
                add_item(entry, None)
            elif ext in archive_ext:
                add_item(entry, "archive")

        # Recursif d'un niveau
        for child in source_path.iterdir():
            if not child.is_dir():
                continue
            for entry in child.iterdir():
                if not entry.is_file():
                    continue
                ext = entry.suffix.lower()
                if ext in allowed_ext:
                    add_item(entry, None)
                elif ext in archive_ext:
                    add_item(entry, "archive")

        return sorted(items, key=lambda x: str(x[0]).lower())

    def _allowed_extensions(self) -> Tuple[str, ...]:
        if self.direction == "iso_to_wbfs":
            return (".iso", ".rvz")
        if self.direction == "wbfs_to_rvz":
            return (".wbfs",)
        if self.direction == "wbfs_to_iso":
            return (".wbfs",)
        return self.SUPPORTED_EXTENSIONS

    def _ensure_temp_extract_folder(self, dest_path: Path) -> Path:
        if self.temp_extract_folder and self.temp_extract_folder.exists():
            return self.temp_extract_folder

        temp_root = dest_path / "TEMP"
        temp_root.mkdir(parents=True, exist_ok=True)

        self.temp_extract_folder = Path(
            tempfile.mkdtemp(prefix="B2PC_wbfs_", dir=str(temp_root))
        )
        self.log(f"📂 Dossier temporaire cree: {self.temp_extract_folder}")
        return self.temp_extract_folder

    def _ensure_work_folder(self, dest_path: Path) -> Path:
        if not self.temp_extract_folder:
            self._ensure_temp_extract_folder(dest_path)

        # mypy: self.temp_extract_folder is guaranteed here
        work_folder = self.temp_extract_folder / "work"
        work_folder.mkdir(parents=True, exist_ok=True)
        return work_folder

    def _prepare_input_for_wbfs(self, input_file: Path, dest_path: Path) -> Tuple[bool, Path]:
        if input_file.suffix.lower() != ".rvz":
            return True, input_file

        self.log(f"🔄 Conversion intermediaire RVZ -> ISO: {input_file.name}")

        work_folder = self._ensure_work_folder(dest_path)
        temp_iso = work_folder / f"{input_file.stem}.iso"

        try:
            if temp_iso.exists():
                temp_iso.unlink()
        except Exception:
            pass

        args = [
            "convert",
            "-f",
            "iso",
            "-i",
            str(input_file),
            "-o",
            str(temp_iso),
        ]

        if not self.run_tool("dolphin-tool.exe", args, show_output=True):
            self.log(f"❌ Echec conversion RVZ -> ISO: {input_file.name}")
            return False, input_file

        if not temp_iso.exists():
            self.log(f"❌ ISO intermediaire introuvable: {temp_iso.name}")
            return False, input_file

        return True, temp_iso

    def _snapshot_outputs(self, folder: Path) -> Dict[str, Tuple[int, float]]:
        snapshot: Dict[str, Tuple[int, float]] = {}
        for p in folder.iterdir():
            if not p.is_file():
                continue
            if p.suffix.lower() not in (".iso", ".wbfs", ".rvz", ".txt"):
                continue
            stat = p.stat()
            snapshot[p.name] = (int(stat.st_size), float(stat.st_mtime))
        return snapshot

    def _detect_output_changes(
        self,
        before: Dict[str, Tuple[int, float]],
        after: Dict[str, Tuple[int, float]],
    ) -> List[str]:
        changes: List[str] = []
        for name, meta in after.items():
            if name not in before or before[name] != meta:
                changes.append(name)
        return sorted(changes)

    def _is_under_temp_workspace(self, path: Path) -> bool:
        if not self.temp_extract_folder:
            return False
        try:
            path.resolve().relative_to(self.temp_extract_folder.resolve())
            return True
        except Exception:
            return False

    def _snapshot_generated_files(self, root: Path, extension: str) -> Dict[str, Tuple[int, float]]:
        snapshot: Dict[str, Tuple[int, float]] = {}
        if not root.exists() or not root.is_dir():
            return snapshot

        for p in root.rglob(f"*{extension}"):
            if not p.is_file():
                continue
            try:
                rel = str(p.relative_to(root))
                stat = p.stat()
                snapshot[rel] = (int(stat.st_size), float(stat.st_mtime))
            except Exception:
                continue
        return snapshot

    def _move_generated_from_temp(
        self,
        temp_root: Path,
        before: Dict[str, Tuple[int, float]],
        after: Dict[str, Tuple[int, float]],
        dest_path: Path,
    ) -> List[str]:
        moved: List[str] = []

        for rel, meta in after.items():
            if rel in before and before[rel] == meta:
                continue

            src = temp_root / rel
            dst = dest_path / rel

            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.exists():
                    dst.unlink()
                shutil.move(str(src), str(dst))
                moved.append(rel.replace("\\", "/"))
            except Exception as e:
                self.log(f"❌ Echec deplacement sortie depuis TEMP: {e}")

        if moved:
            self.log(f"📦 Sortie deplacee depuis TEMP: {len(moved)} fichier(s)")

        return sorted(moved)

    def _cleanup_empty_parent_folders(self, start_folder: Path, stop_folder: Path):
        """Try to delete empty folders from start_folder up to (but excluding) stop_folder."""
        current = start_folder
        while True:
            if current == stop_folder:
                break
            try:
                current.rmdir()
            except Exception:
                break
            parent = current.parent
            if parent == current:
                break
            current = parent

    def _move_generated_iso_to_destination(
        self,
        source_root: Path,
        before: Dict[str, Tuple[int, float]],
        after: Dict[str, Tuple[int, float]],
        dest_path: Path,
    ) -> List[str]:
        moved: List[str] = []

        for rel, meta in after.items():
            if rel in before and before[rel] == meta:
                continue

            src = source_root / rel
            if src.parent != source_root:
                dst_name = f"{src.parent.name}.iso"
            else:
                dst_name = src.name
            dst = dest_path / dst_name

            try:
                src_resolved = src.resolve()
                dst_resolved = dst.resolve()
                if src_resolved == dst_resolved:
                    moved.append(dst.name)
                    continue
            except Exception:
                pass

            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.exists():
                    dst.unlink()
                shutil.move(str(src), str(dst))
                moved.append(dst.name)
                self._cleanup_empty_parent_folders(src.parent, source_root)
            except Exception as e:
                self.log(f"❌ Echec deplacement sortie ISO vers destination: {e}")

        if moved:
            self.log(f"📦 Sortie ISO deplacee vers destination: {len(moved)} fichier(s)")

        return sorted(set(moved))

    def _convert_iso_to_rvz(self, iso_file: Path, dest_path: Path) -> Tuple[bool, Optional[str]]:
        rvz_file = dest_path / f"{iso_file.stem}.rvz"
        if rvz_file.exists():
            self.log(f"⏭️ RVZ deja existant : {rvz_file.name}")
            return True, rvz_file.name

        args = [
            "convert",
            "-f", "rvz",
            "-c", "zstd",
            "-l", "5",
            "-b", "131072",
            "-i", str(iso_file),
            "-o", str(rvz_file),
        ]
        if self.run_tool("dolphin-tool.exe", args, show_output=True):
            self.log(f"🐬 Converti en RVZ : {iso_file.name}")
            return True, rvz_file.name

        self.log(f"❌ Echec conversion ISO -> RVZ: {iso_file.name}")
        return False, None

    def _convert_wbfs_to_rvz_one(self, input_file: Path, dest_path: Path) -> Tuple[bool, List[str]]:
        before = self._snapshot_outputs(dest_path)

        temp_before = self._snapshot_generated_files(input_file.parent, ".iso")
        ok = self.run_tool("wbfs_file.exe", [str(input_file)], cwd=str(dest_path), show_output=True)
        if not ok:
            return False, []

        temp_after = self._snapshot_generated_files(input_file.parent, ".iso")
        moved_iso = self._move_generated_iso_to_destination(
            input_file.parent,
            temp_before,
            temp_after,
            dest_path,
        )

        iso_candidates = [
            dest_path / name
            for name in moved_iso
            if (dest_path / name).exists() and name.lower().endswith(".iso")
        ]

        if not iso_candidates:
            self.log("❌ Sortie ISO introuvable pour conversion RVZ")
            return False, []

        produced_names: List[str] = []
        for iso_file in iso_candidates:
            conv_ok, rvz_name = self._convert_iso_to_rvz(iso_file, dest_path)
            if not conv_ok:
                return False, []
            if rvz_name:
                produced_names.append(rvz_name)

            try:
                iso_file.unlink()
                self.log(f"🧹 ISO intermediaire supprime: {iso_file.name}")
            except Exception:
                pass

        after = self._snapshot_outputs(dest_path)
        changes = self._detect_output_changes(before, after)
        for name in produced_names:
            if name not in changes:
                changes.append(name)
        changes.sort()
        return True, changes

    def _convert_one_file(self, input_file: Path, dest_path: Path) -> Tuple[bool, List[str]]:
        if self.direction == "wbfs_to_rvz":
            direction = "WBFS -> ISO -> RVZ"
        elif input_file.suffix.lower() == ".rvz":
            direction = "RVZ -> ISO -> WBFS"
        elif input_file.suffix.lower() == ".iso":
            direction = "ISO -> WBFS"
        else:
            direction = "WBFS -> ISO"
        self.log(f"🔄 Conversion {direction}: {input_file.name}")

        if self.direction == "wbfs_to_rvz":
            return self._convert_wbfs_to_rvz_one(input_file, dest_path)

        prepared_ok, prepared_input = self._prepare_input_for_wbfs(input_file, dest_path)
        if not prepared_ok:
            return False, []

        expected_output_ext = ".wbfs" if prepared_input.suffix.lower() == ".iso" else ".iso"
        temp_before = self._snapshot_generated_files(prepared_input.parent, expected_output_ext)

        before = self._snapshot_outputs(dest_path)
        ok = self.run_tool("wbfs_file.exe", [str(prepared_input)], cwd=str(dest_path), show_output=True)
        if not ok:
            return False, []

        temp_after = self._snapshot_generated_files(prepared_input.parent, expected_output_ext)
        moved_outputs: List[str] = []

        if expected_output_ext == ".iso":
            moved_outputs = self._move_generated_iso_to_destination(
                prepared_input.parent,
                temp_before,
                temp_after,
                dest_path,
            )
            try:
                parent_is_dest = prepared_input.parent.resolve() == dest_path.resolve()
            except Exception:
                parent_is_dest = prepared_input.parent == dest_path

            if not parent_is_dest and not moved_outputs:
                self.log("❌ Sortie ISO introuvable apres conversion")
                return False, []
        elif self._is_under_temp_workspace(prepared_input.parent):
            moved_outputs = self._move_generated_from_temp(
                prepared_input.parent,
                temp_before,
                temp_after,
                dest_path,
            )
            if not moved_outputs:
                self.log("❌ Sortie introuvable dans TEMP apres conversion")
                return False, []

        after = self._snapshot_outputs(dest_path)
        changes = self._detect_output_changes(before, after)
        for output_name in moved_outputs:
            leaf_name = Path(output_name).name
            if leaf_name not in changes:
                changes.append(leaf_name)
        changes.sort()
        return True, changes

    def convert(self) -> dict:
        dest_path = Path(self.dest_folder)
        dest_path.mkdir(exist_ok=True)

        try:
            source_files = self._collect_source_items()

            if self.direction == "iso_to_wbfs":
                mode_label = "[WII] ISO > WBFS"
                source_label = "ISO/RVZ"
            elif self.direction == "wbfs_to_rvz":
                mode_label = "[WII] WBFS > RVZ"
                source_label = "WBFS"
            elif self.direction == "wbfs_to_iso":
                mode_label = "[WII] WBFS > ISO"
                source_label = "WBFS"
            else:
                mode_label = "[WII] WBFS <> ISO"
                source_label = "WBFS/ISO"

            self.log(f"🎮 Traitement de {len(source_files)} source(s) {source_label}")

            converted = 0
            errors = 0
            total_sources = max(1, len(source_files))

            for i, (source_item, extract_type) in enumerate(source_files):
                if self.check_should_stop():
                    break

                self.progress((i / total_sources) * 100, f"Traitement {mode_label} {i+1}/{len(source_files)}")

                if extract_type is None:
                    input_files = [source_item]
                    self.log(f"📄 Traitement direct: {source_item.name}")
                elif extract_type == "archive":
                    self.log(f"📦 Extraction de l'archive: {source_item.name}")
                    try:
                        self._ensure_temp_extract_folder(dest_path)
                        extracted_folder = self.extract_single_archive(source_item)
                        input_files = self._list_convertible_files(extracted_folder)
                        self.log(f"📁 Trouve {len(input_files)} fichier(s) ISO/WBFS dans l'archive")
                    except Exception as e:
                        self.log(f"❌ Echec extraction {source_item.name}: {e}")
                        errors += 1
                        continue
                else:
                    input_files = []

                for input_file in input_files:
                    if self.check_should_stop():
                        break

                    ok, changed_outputs = self._convert_one_file(input_file, dest_path)
                    if not ok:
                        errors += 1
                        self.log(f"❌ Echec conversion: {input_file.name}")
                        continue

                    converted += 1
                    self.log(f"✅ Converti: {input_file.name}")

                    if changed_outputs:
                        preview = ", ".join(changed_outputs[:3])
                        suffix = "" if len(changed_outputs) <= 3 else f" (+{len(changed_outputs) - 3})"
                        self.log(f"📦 Sortie detectee: {preview}{suffix}")
                    else:
                        self.log("ℹ️ Aucune sortie detectee automatiquement (fichier peut deja exister)")

            if self.should_stop:
                self.log("🛑 Conversion arretee par l'utilisateur")

            self.progress(100, f"Conversion {mode_label} terminee")
            return {
                "converted_games": converted,
                "error_count": errors,
                "total_files": len(source_files),
                "stopped": self.should_stop,
            }
        finally:
            self.cleanup_temp_folder()
