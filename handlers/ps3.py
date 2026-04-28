from .base import ConversionHandler
from pathlib import Path
import os
import subprocess
import re
import time
import zipfile
import shutil
from typing import List, Optional, Tuple


class Ps3DecryptHandler(ConversionHandler):
    """Handler pour decrypter et extraire les ISOs PS3 (Redump)."""

    KEY_ARCHIVE_NAMES = ("ps3_dec.zip", "ps3dec.zip")

    def _get_bundled_7z_variants(self) -> List[Path]:
        from main import resource_path

        # Priorite aux variantes 7z.exe (moteur complet), puis fallback 7za.exe.
        return [
            Path(resource_path("ressources/7z/7z.exe")),
            Path(resource_path("ressources/7z/x64/7z.exe")),
            Path(resource_path("ressources/7z/x86/7z.exe")),
            Path(resource_path("ressources/7z.exe")),
            Path(resource_path("ressources/7za.exe")),
        ]

    def validate_tools(self) -> bool:
        """Valide les outils minimaux necessaires au traitement PS3."""
        from main import resource_path

        ps3dec_path = Path(resource_path("ressources/ps3dec_win.exe"))
        if not ps3dec_path.exists():
            self.log("❌ Outil manquant : ps3dec_win.exe")
            return False

        bundled_extractors = [path for path in self._get_bundled_7z_variants() if path.exists()]
        installed_extractors = [
            Path(r"C:\Program Files\7-Zip\7z.exe"),
            Path(r"C:\Program Files (x86)\7-Zip\7z.exe"),
            Path(r"C:\Program Files\7-Zip\7za.exe"),
            Path(r"C:\Program Files (x86)\7-Zip\7za.exe"),
        ]

        has_path_extractor = bool(shutil.which("7z")) or bool(shutil.which("7za"))
        has_extractor = (
            bool(bundled_extractors)
            or any(path.exists() for path in installed_extractors)
            or has_path_extractor
        )
        if not has_extractor:
            self.log("❌ Outil manquant : 7z.exe/7za.exe (embarque ou installe)")
            return False

        self.log("✅ Outils PS3 detectes")
        return True

    def _ensure_temp_folder(self) -> Path:
        if not self.temp_extract_folder:
            self.temp_extract_folder = self._create_temp_workspace("B2PC_ps3_")
        return self.temp_extract_folder

    def _candidate_bases(self, iso_file: Path, archive_name: Optional[str]) -> List[str]:
        candidates: List[str] = []

        def add_candidate(name: Optional[str]):
            if not name:
                return
            clean = str(name).strip()
            if not clean:
                return
            if clean.lower().endswith(".dkey"):
                clean = clean[:-5]
            if clean not in candidates:
                candidates.append(clean)

        if archive_name:
            add_candidate(Path(archive_name).stem)
        add_candidate(iso_file.stem)

        # Certains dumps ajoutent un suffixe decryption/decrypted au nom ISO.
        if iso_file.stem.lower().endswith("_decrypted"):
            add_candidate(iso_file.stem[:-10])

        return candidates

    def _find_local_dkey(self, search_dir: Path, candidate_bases: List[str]) -> Optional[Path]:
        for base_name in candidate_bases:
            dkey_path = search_dir / f"{base_name}.dkey"
            if dkey_path.exists():
                self.log(f"🔑 Cle locale trouvee: {dkey_path.name}")
                return dkey_path

        dkey_files = sorted(search_dir.glob("*.dkey"))
        if dkey_files:
            self.log(f"🔑 Cle locale utilisee: {dkey_files[0].name}")
            return dkey_files[0]

        return None

    def _find_dkey_in_zip(self, zip_path: Path, candidate_bases: List[str]) -> Optional[Path]:
        if not zip_path.exists():
            return None

        self.log(f"📦 Recherche de cle dans: {zip_path.name}")
        temp_folder = self._ensure_temp_folder()

        try:
            with zipfile.ZipFile(zip_path, "r") as archive:
                dkey_entries = [
                    entry
                    for entry in archive.namelist()
                    if entry and entry.lower().endswith(".dkey")
                ]
                if not dkey_entries:
                    return None

                entries_by_fullname = {entry.lower(): entry for entry in dkey_entries}
                entries_by_basename = {}
                for entry in dkey_entries:
                    entries_by_basename[Path(entry).name.lower()] = entry

                for base_name in candidate_bases:
                    dkey_name = f"{base_name}.dkey"
                    dkey_name_lower = dkey_name.lower()

                    matching_entry = entries_by_basename.get(dkey_name_lower)
                    if not matching_entry:
                        matching_entry = entries_by_fullname.get(dkey_name_lower)
                    if not matching_entry:
                        continue

                    local_dkey = temp_folder / Path(matching_entry).name
                    local_dkey.write_bytes(archive.read(matching_entry))
                    self.log(f"🔑 Cle trouvee dans zip: {local_dkey.name}")
                    return local_dkey
        except zipfile.BadZipFile:
            self.log(f"❌ Archive invalide: {zip_path.name}")
        except Exception as e:
            self.log(f"⚠️ Lecture zip impossible ({zip_path.name}): {e}")

        return None

    def _get_local_key_archives(self, search_dir: Path) -> List[Path]:
        from main import resource_path

        archives: List[Path] = []
        seen = set()

        candidate_folders = [search_dir, Path(self.source_folder)]
        for archive_name in self.KEY_ARCHIVE_NAMES:
            resource_archive = Path(resource_path(f"ressources/{archive_name}"))
            candidate_folders.append(resource_archive.parent)

        for folder in candidate_folders:
            if not folder or not folder.exists():
                continue
            for archive_name in self.KEY_ARCHIVE_NAMES:
                archive_path = (folder / archive_name).resolve()
                key = str(archive_path).lower()
                if archive_path.exists() and key not in seen:
                    archives.append(archive_path)
                    seen.add(key)

        return archives

    def _resolve_dkey(self, iso_file: Path, archive_name: Optional[str], search_dir: Path) -> Optional[Path]:
        candidate_bases = self._candidate_bases(iso_file, archive_name)

        local_folders = [search_dir, Path(self.source_folder)]
        seen = set()
        for folder in local_folders:
            key = str(folder.resolve()).lower() if folder.exists() else str(folder).lower()
            if key in seen:
                continue
            seen.add(key)

            if folder.exists():
                local_dkey = self._find_local_dkey(folder, candidate_bases)
                if local_dkey:
                    return local_dkey

        for key_archive in self._get_local_key_archives(search_dir):
            archived_dkey = self._find_dkey_in_zip(key_archive, candidate_bases)
            if archived_dkey:
                return archived_dkey

        return None

    def _read_dkey_value(self, dkey_path: Path) -> Optional[str]:
        try:
            key_raw = dkey_path.read_text(encoding="utf-8", errors="ignore")
            key_value = re.sub(r"\s+", "", key_raw)
            if not key_value:
                return None
            return key_value
        except Exception as e:
            self.log(f"❌ Impossible de lire la cle {dkey_path.name}: {e}")
            return None

    def _extract_percent_from_output(self, line: str, tool_name: str) -> Optional[float]:
        percent = self._extract_progress(line, tool_name)
        if percent is not None:
            return max(0.0, min(100.0, percent))

        generic_percent = re.search(r"(\d+(?:\.\d+)?)\s*%", line)
        if generic_percent:
            try:
                value = float(generic_percent.group(1))
                return max(0.0, min(100.0, value))
            except ValueError:
                pass

        ratio_progress = re.search(r"(\d+)\s*/\s*(\d+)", line)
        if ratio_progress:
            try:
                done = float(ratio_progress.group(1))
                total = float(ratio_progress.group(2))
                if total > 0:
                    value = (done / total) * 100.0
                    return max(0.0, min(100.0, value))
            except ValueError:
                pass

        return None

    def _should_suppress_line(self, line: str, progress_tool: str) -> bool:
        tool = (progress_tool or "").lower()
        text = (line or "").strip().lower()

        # 7z can report benign UDF header warnings on valid PS3 images.
        if "7z" in tool:
            if "headers error" in text:
                return True

            # Noise lines emitted with benign UDF header issues.
            benign_prefixes = (
                "errors:",
                "warnings:",
                "path =",
                "created =",
                "filesetnumber:",
                "filesetdescnumber:",
                "archives with errors:",
                "warnings:",
                "open errors:",
            )

            for prefix in benign_prefixes:
                if text.startswith(prefix):
                    return True

        return False

    def _run_process(
        self,
        cmd: List[str],
        label: str,
        allow_returncodes: Optional[List[int]] = None,
        progress_range: Optional[Tuple[float, float]] = None,
        progress_tool: str = "7za.exe",
        progress_text: Optional[str] = None,
    ) -> bool:
        if allow_returncodes is None:
            allow_returncodes = [0]

        self.log(f"🔧 {label}")

        last_mapped_progress: Optional[float] = None
        line_fallback_progress = 0.0

        def emit_progress(raw_percent: float):
            nonlocal last_mapped_progress
            if progress_range is None:
                return

            start, end = progress_range
            clamped = max(0.0, min(100.0, raw_percent))
            mapped = start + ((end - start) * (clamped / 100.0))

            if last_mapped_progress is not None and mapped <= last_mapped_progress:
                return

            last_mapped_progress = mapped
            self.progress(mapped, progress_text or label)

        emit_progress(0.0)

        flags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        try:
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                creationflags=flags,
            )

            if self.current_process.stdout:
                while True:
                    if self.check_should_stop():
                        self.current_process.terminate()
                        return False

                    line = self.current_process.stdout.readline()
                    if line:
                        clean_line = line.strip()
                        if clean_line:
                            if self._should_suppress_line(clean_line, progress_tool):
                                continue

                            percent = self._extract_percent_from_output(clean_line, progress_tool)
                            if percent is not None:
                                emit_progress(percent)
                            elif progress_range is not None and line_fallback_progress < 95.0:
                                line_fallback_progress += 1.0
                                emit_progress(line_fallback_progress)

                            if self._is_important_message(clean_line, progress_tool):
                                self.log(f"   {clean_line}")
                    elif self.current_process.poll() is not None:
                        break

            self.current_process.wait()
            code = self.current_process.returncode
            if code in allow_returncodes:
                emit_progress(100.0)
                return True

            self.log(f"❌ Commande terminee avec erreur (code: {code})")
            return False
        except Exception as e:
            self.log(f"❌ Erreur execution commande: {e}")
            return False
        finally:
            self.current_process = None

    def _decrypt_iso(
        self,
        iso_file: Path,
        decrypted_iso: Path,
        key_value: str,
        progress_start: float,
        progress_end: float,
    ) -> bool:
        from main import resource_path

        ps3dec_exe = Path(resource_path("ressources/ps3dec_win.exe"))
        if not ps3dec_exe.exists():
            self.log("❌ ps3dec_win.exe introuvable")
            return False

        cmd = [
            str(ps3dec_exe),
            "d",
            "key",
            key_value,
            str(iso_file),
            str(decrypted_iso),
        ]

        return self._run_process(
            cmd,
            f"Decryptage PS3: {iso_file.name}",
            progress_range=(progress_start, progress_end),
            progress_tool="ps3dec_win.exe",
            progress_text=f"Decryptage PS3: {iso_file.name}",
        )

    def _extract_decrypted_iso(
        self,
        decrypted_iso: Path,
        output_folder: Path,
        progress_start: float,
        progress_end: float,
    ) -> bool:
        if not decrypted_iso.exists():
            self.log(f"❌ ISO decrypte introuvable: {decrypted_iso}")
            return False

        seven_zip_cmd = self._resolve_ready_7z_binary(decrypted_iso, timeout_sec=45)
        if seven_zip_cmd:
            self.log(f"🧰 Moteur 7z utilise: {seven_zip_cmd}")
        else:
            self.log("⚠️ Aucun moteur 7z compatible detecte pour cet ISO")

        def reset_output_folder() -> bool:
            try:
                if output_folder.exists():
                    shutil.rmtree(output_folder)
                output_folder.mkdir(parents=True, exist_ok=True)
                return True
            except Exception as e:
                self.log(f"❌ Impossible de preparer le dossier cible {output_folder.name}: {e}")
                return False

        def has_valid_ps3_layout() -> bool:
            if not output_folder.exists():
                return False

            ps3_game_root = output_folder / "PS3_GAME"
            if ps3_game_root.is_dir():
                return True

            for path in output_folder.rglob("PS3_GAME"):
                if path.is_dir():
                    return True

            return False

        if seven_zip_cmd:
            attempts = [
                ("auto", []),
                ("iso", ["-tiso"]),
                ("udf", ["-tudf"]),
            ]

            for attempt_index, (attempt_name, type_args) in enumerate(attempts):
                if not reset_output_folder():
                    return False

                fraction_start = attempt_index / len(attempts)
                fraction_end = (attempt_index + 1) / len(attempts)
                attempt_start = progress_start + ((progress_end - progress_start) * fraction_start)
                attempt_end = progress_start + ((progress_end - progress_start) * fraction_end)

                cmd = [
                    seven_zip_cmd,
                    "x",
                    *type_args,
                    str(decrypted_iso),
                    f"-o{output_folder}",
                    "-y",
                ]

                ok = self._run_process(
                    cmd,
                    f"Extraction ISO PS3 ({attempt_name}) vers: {output_folder.name}",
                    allow_returncodes=[0, 1, 2],
                    progress_range=(attempt_start, attempt_end),
                    progress_tool="7za.exe",
                    progress_text=f"Extraction PS3 ({attempt_name}): {output_folder.name}",
                )
                if not ok:
                    continue

                if has_valid_ps3_layout():
                    return True

                self.log(
                    f"⚠️ Extraction ({attempt_name}) terminee sans structure PS3 valide (PS3_GAME absent), nouvelle tentative..."
                )
                time.sleep(1.5)

        if os.name == "nt":
            self.log("🔄 Tentative fallback extraction via montage ISO Windows...")
            if not reset_output_folder():
                return False

            if self._extract_iso_via_windows_mount(
                decrypted_iso,
                output_folder,
                progress_start=progress_start,
                progress_end=progress_end,
            ) and has_valid_ps3_layout():
                return True

            self.log("⚠️ Fallback montage ISO termine sans structure PS3 valide")

        return False

    def _get_7z_candidates(self) -> List[str]:
        candidates: List[str] = []

        for bundled in self._get_bundled_7z_variants():
            if bundled.exists():
                candidates.append(str(bundled))

        common_paths = [
            Path(r"C:\Program Files\7-Zip\7z.exe"),
            Path(r"C:\Program Files (x86)\7-Zip\7z.exe"),
            Path(r"C:\Program Files\7-Zip\7za.exe"),
            Path(r"C:\Program Files (x86)\7-Zip\7za.exe"),
        ]
        for path in common_paths:
            if path.exists():
                candidates.append(str(path))

        # Fallback PATH si un alias est disponible.
        candidates.extend(["7z", "7za", "7z.exe", "7za.exe"])

        unique: List[str] = []
        seen = set()
        for candidate in candidates:
            key = candidate.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(candidate)

        return unique

    def _is_iso_listable_with_7z(self, seven_zip_cmd: str, iso_path: Path) -> bool:
        flags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        try:
            probes = [
                [seven_zip_cmd, "l", str(iso_path)],
                [seven_zip_cmd, "l", "-tiso", str(iso_path)],
                [seven_zip_cmd, "l", "-tudf", str(iso_path)],
            ]

            for probe in probes:
                result = subprocess.run(
                    probe,
                    capture_output=True,
                    text=True,
                    creationflags=flags,
                    timeout=15,
                )
                if result.returncode != 0:
                    continue

                stdout = (result.stdout or "").lower()
                stderr = (result.stderr or "").lower()
                if (
                    "can not open the file as archive" in stdout
                    or "can not open the file as archive" in stderr
                    or "cannot open the file as archive" in stdout
                    or "cannot open the file as archive" in stderr
                    or "error:" in stdout
                    or "error:" in stderr
                ):
                    continue
                return True

            return False
        except Exception:
            return False

    def _is_7z_binary_available(self, seven_zip_cmd: str) -> bool:
        flags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        try:
            result = subprocess.run(
                [seven_zip_cmd, "i"],
                capture_output=True,
                text=True,
                creationflags=flags,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _resolve_ready_7z_binary(self, iso_path: Path, timeout_sec: int = 45) -> Optional[str]:
        candidates = self._get_7z_candidates()
        if not candidates:
            return None

        first_available_candidate: Optional[str] = None

        deadline = time.monotonic() + timeout_sec
        attempt = 0
        while time.monotonic() < deadline:
            if self.check_should_stop():
                return None

            attempt += 1
            for candidate in candidates:
                if first_available_candidate is None and self._is_7z_binary_available(candidate):
                    first_available_candidate = candidate

                if self._is_iso_listable_with_7z(candidate, iso_path):
                    if attempt > 1:
                        self.log(f"✅ ISO pret pour 7z apres {attempt} tentative(s)")
                    return candidate

            if attempt == 1:
                self.log("⏳ Attente disponibilite ISO/moteur 7z...")
            time.sleep(2)

        # Fallback: utiliser un moteur disponible meme si le test de listing a echoue.
        # Les tentatives d'extraction (auto/iso/udf) restent l'arbitre final.
        if first_available_candidate:
            self.log("⚠️ ISO non listable detecte, fallback sur moteur 7z disponible")
            return first_available_candidate

        return None

    def _extract_iso_via_windows_mount(
        self,
        decrypted_iso: Path,
        output_folder: Path,
        progress_start: float,
        progress_end: float,
    ) -> bool:
        if os.name != "nt":
            return False

        def ps_quote(value: str) -> str:
            return value.replace("'", "''")

        iso_ps = ps_quote(str(decrypted_iso))
        dst_ps = ps_quote(str(output_folder))

        script = (
            "$ErrorActionPreference='Stop'; "
            f"$iso='{iso_ps}'; "
            f"$dst='{dst_ps}'; "
            "$null = New-Item -ItemType Directory -Path $dst -Force; "
            "$mount = Mount-DiskImage -ImagePath $iso -PassThru; "
            "try { "
            "$vol = $mount | Get-Volume; "
            "$drive = $vol.DriveLetter; "
            "if (-not $drive) { throw \"Aucune lettre de lecteur pour l'ISO monte\" }; "
            "$srcRoot = \"$($drive):\\\"; "
            "if (-not (Test-Path $srcRoot)) { throw \"Lecteur monte inaccessible: $srcRoot\" }; "
            "$null = & robocopy $srcRoot $dst /E /COPY:DAT /DCOPY:DAT /R:4 /W:2 /NFL /NDL /NJH /NJS /NP /MT:8; "
            "$rc = $LASTEXITCODE; "
            "if ($rc -ge 8) { throw \"robocopy a echoue (code=$rc)\" }; "
            "} finally { "
            "Dismount-DiskImage -ImagePath $iso | Out-Null; "
            "}"
        )

        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ]

        return self._run_process(
            cmd,
            f"Extraction ISO PS3 (mount) vers: {output_folder.name}",
            allow_returncodes=[0],
            progress_range=(progress_start, progress_end),
            progress_tool="7za.exe",
            progress_text=f"Extraction PS3 (mount): {output_folder.name}",
        )

    def convert(self) -> dict:
        dest_path = Path(self.dest_folder)
        dest_path.mkdir(exist_ok=True)

        try:
            source_files = self.get_all_source_files(".iso")
            self.log(f"🎮 Traitement de {len(source_files)} source(s) PS3")

            decrypted_games = 0
            errors = 0

            for i, (source_item, extract_type) in enumerate(source_files):
                if self.check_should_stop():
                    break

                total = max(1, len(source_files))
                item_start = (i / total) * 100.0
                item_end = ((i + 1) / total) * 100.0
                item_span = max(1.0, item_end - item_start)
                self.progress(item_start, f"Traitement PS3 {i+1}/{len(source_files)}")

                archive_name = None
                key_search_dir = Path(self.source_folder)

                if extract_type is None:
                    iso_files = [source_item]
                    self.log(f"📄 Traitement direct: {source_item.name}")
                elif extract_type == "archive":
                    archive_name = source_item.name
                    self.log(f"📦 Extraction archive: {archive_name}")
                    try:
                        extracted_folder = self.extract_single_archive(source_item)
                        key_search_dir = extracted_folder
                        iso_files = [
                            p
                            for p in extracted_folder.iterdir()
                            if p.is_file()
                            and p.suffix.lower() == ".iso"
                            and not p.name.lower().endswith("_decrypted.iso")
                        ]
                        self.log(f"📁 Trouve {len(iso_files)} ISO(s) dans l'archive")
                    except Exception as e:
                        self.log(f"❌ Echec extraction {archive_name}: {e}")
                        errors += 1
                        continue
                else:
                    continue

                iso_total = max(1, len(iso_files))

                for iso_index, iso_file in enumerate(iso_files):
                    if self.check_should_stop():
                        break

                    iso_start = item_start + (item_span * (iso_index / iso_total))
                    iso_end = item_start + (item_span * ((iso_index + 1) / iso_total))

                    def map_iso_progress(local_percent: float) -> float:
                        clamped = max(0.0, min(100.0, local_percent))
                        return iso_start + ((iso_end - iso_start) * (clamped / 100.0))

                    if iso_file.name.lower().endswith("_decrypted.iso"):
                        self.log(f"⏭️ Ignore (deja decrypte): {iso_file.name}")
                        self.progress(map_iso_progress(100.0), f"ISO ignore: {iso_file.name}")
                        continue

                    game_name = iso_file.stem
                    game_folder = dest_path / f"{game_name}.ps3"

                    if game_folder.exists() and (game_folder / "PS3_GAME").exists():
                        self.log(f"⏭️ Deja extrait: {game_folder.name}")
                        self.progress(map_iso_progress(100.0), f"Deja extrait: {game_folder.name}")
                        continue

                    self.progress(map_iso_progress(5.0), f"Recherche de cle: {iso_file.name}")

                    dkey_path = self._resolve_dkey(iso_file, archive_name, key_search_dir)
                    if not dkey_path:
                        self.log(f"❌ Aucune cle .dkey trouvee pour {iso_file.name}")
                        self.progress(map_iso_progress(100.0), f"Cle introuvable: {iso_file.name}")
                        errors += 1
                        continue

                    key_value = self._read_dkey_value(dkey_path)
                    if not key_value:
                        self.log(f"❌ Cle invalide: {dkey_path.name}")
                        self.progress(map_iso_progress(100.0), f"Cle invalide: {dkey_path.name}")
                        errors += 1
                        continue

                    self.progress(map_iso_progress(10.0), f"Cle chargee: {dkey_path.name}")

                    decrypted_iso = dest_path / f"{game_name}_decrypted.iso"
                    if decrypted_iso.exists():
                        try:
                            decrypted_iso.unlink()
                        except Exception as e:
                            self.log(f"⚠️ Impossible de supprimer l'ancien ISO decrypte: {e}")

                    if not self._decrypt_iso(
                        iso_file,
                        decrypted_iso,
                        key_value,
                        progress_start=map_iso_progress(10.0),
                        progress_end=map_iso_progress(75.0),
                    ):
                        self.log(f"❌ Echec decryptage PS3: {iso_file.name}")
                        self.progress(map_iso_progress(100.0), f"Echec decryptage: {iso_file.name}")
                        errors += 1
                        continue

                    if not self._extract_decrypted_iso(
                        decrypted_iso,
                        game_folder,
                        progress_start=map_iso_progress(75.0),
                        progress_end=map_iso_progress(98.0),
                    ):
                        self.log(f"❌ Echec extraction ISO decrypte: {decrypted_iso.name}")
                        self.log(f"ℹ️ ISO decrypte conserve pour diagnostic: {decrypted_iso}")
                        self.progress(map_iso_progress(100.0), f"Echec extraction: {decrypted_iso.name}")
                        errors += 1
                        continue

                    try:
                        decrypted_iso.unlink()
                    except Exception as e:
                        self.log(f"⚠️ Nettoyage ISO decrypte impossible: {e}")

                    decrypted_games += 1
                    self.log(f"✅ Jeu PS3 decrypte et extrait: {game_folder.name}")
                    if extract_type is None:
                        self.delete_source_after_success(iso_file)
                    self.progress(map_iso_progress(100.0), f"Termine: {game_folder.name}")

                if self.check_should_stop():
                    break

            if self.should_stop:
                self.log("🛑 Conversion arretee par l'utilisateur")

            return {
                "converted_games": decrypted_games,
                "error_count": errors,
                "total_files": len(source_files),
                "stopped": self.should_stop,
            }
        finally:
            self.cleanup_temp_folder()
