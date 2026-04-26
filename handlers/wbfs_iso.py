from pathlib import Path
from typing import Dict, List, Optional, Tuple
import shutil

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
            return (".iso",)
        if self.direction == "wbfs_to_iso":
            return (".wbfs",)
        return self.SUPPORTED_EXTENSIONS

    def _iter_files_depth_one(self, root: Path, extensions: Tuple[str, ...]) -> List[Path]:
        files: List[Path] = []
        if not root.exists() or not root.is_dir():
            return files

        ext_set = set(ext.lower() for ext in extensions)

        # Root level
        for p in root.iterdir():
            if p.is_file() and p.suffix.lower() in ext_set:
                files.append(p)

        # One subfolder level
        for child in root.iterdir():
            if not child.is_dir():
                continue
            for p in child.iterdir():
                if p.is_file() and p.suffix.lower() in ext_set:
                    files.append(p)

        return files

    def _snapshot_outputs(self, folder: Path) -> Dict[str, Tuple[int, float]]:
        snapshot: Dict[str, Tuple[int, float]] = {}
        for p in folder.iterdir():
            if not p.is_file():
                continue
            if p.suffix.lower() not in (".iso", ".wbfs", ".txt"):
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

    def _snapshot_local_outputs(self, root: Path) -> Dict[str, Tuple[int, float]]:
        snapshot: Dict[str, Tuple[int, float]] = {}
        if not root.exists() or not root.is_dir():
            return snapshot

        for p in self._iter_files_depth_one(root, (".wbfs", ".iso", ".txt")):
            try:
                rel = str(p.relative_to(root))
                stat = p.stat()
                snapshot[rel] = (int(stat.st_size), float(stat.st_mtime))
            except Exception:
                continue
        return snapshot

    def _cleanup_generated_wbfs_folder(self, generated_folder: Path, input_file: Path, dest_path: Path):
        """Remove converter-generated folder when safe after WBFS move."""
        try:
            folder = generated_folder.resolve()
            source_parent = input_file.parent.resolve()
            destination = dest_path.resolve()
        except Exception:
            return

        # Only clean a direct child folder near source, never destination or source root.
        if folder == source_parent or folder == destination or folder.parent != source_parent:
            return

        # Keep safety guard: expected pattern "Title [GAMEID]".
        expected_prefix = f"{input_file.stem} [".lower()
        if not folder.name.lower().startswith(expected_prefix):
            return

        try:
            # Remove auxiliary info files left by wbfs_file.
            for child in list(folder.iterdir()):
                if child.is_file() and child.suffix.lower() == ".txt":
                    child.unlink()

            if not any(folder.iterdir()):
                folder.rmdir()
                self.log(f"🧹 Dossier genere supprime: {folder.name}")
        except Exception:
            # Keep non-empty or protected folders untouched.
            pass

    def _find_created_or_updated_files(
        self,
        root: Path,
        before: Dict[str, Tuple[int, float]],
        after: Dict[str, Tuple[int, float]],
        extension: str,
    ) -> List[Path]:
        results: List[Path] = []
        for rel, meta in after.items():
            if not rel.endswith(extension):
                continue
            if rel not in before or before[rel] != meta:
                results.append(root / rel)

        # Plus recent en premier
        results.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True)
        return results

    def _compute_target_wbfs_name(self, input_file: Path, source_wbfs: Path, dest_path: Path) -> str:
        generated_parent = source_wbfs.parent

        # Preferred naming: folder created by wbfs_file, e.g. "Game Title [GAMEID]".
        if generated_parent != input_file.parent and generated_parent != dest_path:
            folder_name = generated_parent.name.strip()
            if folder_name and not folder_name.lower().startswith("extracted_"):
                return f"{folder_name}.wbfs"

        return f"{input_file.stem}.wbfs"

    def _relocate_wbfs_output(
        self,
        input_file: Path,
        dest_path: Path,
        source_before: Dict[str, Tuple[int, float]],
        source_after: Dict[str, Tuple[int, float]],
    ) -> Optional[str]:
        candidates = self._find_created_or_updated_files(
            input_file.parent,
            source_before,
            source_after,
            ".wbfs",
        )
        if not candidates:
            return None

        source_wbfs = candidates[0]
        target_name = self._compute_target_wbfs_name(input_file, source_wbfs, dest_path)
        target_wbfs = dest_path / target_name

        try:
            if target_wbfs.exists():
                target_wbfs.unlink()
            shutil.move(str(source_wbfs), str(target_wbfs))

            # Try to remove generated source subfolder if it is now empty.
            self._cleanup_generated_wbfs_folder(source_wbfs.parent, input_file, dest_path)

            return target_name
        except Exception as e:
            self.log(f"❌ Echec deplacement sortie WBFS: {e}")
            return None

    def _convert_one_file(self, input_file: Path, dest_path: Path) -> Tuple[bool, List[str]]:
        direction = "ISO -> WBFS" if input_file.suffix.lower() == ".iso" else "WBFS -> ISO"
        self.log(f"🔄 Conversion {direction}: {input_file.name}")

        source_before = self._snapshot_local_outputs(input_file.parent)
        before = self._snapshot_outputs(dest_path)
        ok = self.run_tool("wbfs_file.exe", [str(input_file)], cwd=str(dest_path), show_output=True)
        if not ok:
            return False, []

        source_after = self._snapshot_local_outputs(input_file.parent)

        relocated_name: Optional[str] = None
        if input_file.suffix.lower() == ".iso":
            relocated_name = self._relocate_wbfs_output(
                input_file,
                dest_path,
                source_before,
                source_after,
            )
            if not relocated_name:
                self.log("❌ Fichier WBFS genere introuvable apres conversion")
                return False, []

        after = self._snapshot_outputs(dest_path)
        changes = self._detect_output_changes(before, after)
        if relocated_name and relocated_name not in changes:
            changes.append(relocated_name)
            changes.sort()
        return True, changes

    def convert(self) -> dict:
        dest_path = Path(self.dest_folder)
        dest_path.mkdir(exist_ok=True)

        try:
            source_files = self._collect_source_items()

            if self.direction == "iso_to_wbfs":
                mode_label = "ISO > WBFS"
                source_label = "ISO"
            elif self.direction == "wbfs_to_iso":
                mode_label = "WBFS > ISO"
                source_label = "WBFS"
            else:
                mode_label = "WBFS <> ISO"
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
