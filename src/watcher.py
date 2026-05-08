"""
@file    watcher.py
@project Scan Watcher
@company Nova Network
@date    Mai 2026
@brief   Dateiueberwachung mit watchdog – erkennt neue numerisch benannte PDFs,
         wartet auf stabile Dateigroesse und startet die Verarbeitungs-Pipeline.
"""

import logging
import os
import re
import shutil
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from . import config, ocr, renamer, telemetry

log = logging.getLogger("scan_watcher.watcher")

_session_count = 0
_count_lock = threading.Lock()
_recent_files: list[str] = []
_recent_lock = threading.Lock()
_MAX_RECENT = 20


def get_session_count() -> int:
    return _session_count


def get_recent_files() -> list[str]:
    with _recent_lock:
        return list(_recent_files)


def is_numeric_file(filename: str, extensions: list | None = None, name_pattern: str = "") -> bool:
    """Prueft ob Dateiname dem konfigurierten Muster und der Erweiterung entspricht."""
    p = Path(filename)
    exts = [e.lower() for e in (extensions or [".pdf"])]
    if p.suffix.lower() not in exts:
        return False
    if name_pattern:
        try:
            return bool(re.fullmatch(name_pattern, p.stem))
        except re.error:
            pass
    return p.stem.isdigit()


def is_numeric_pdf(filename: str) -> bool:
    return is_numeric_file(filename, [".pdf"])


def _wait_for_stable(path: str, timeout: int = 30) -> bool:
    """Wartet bis der Scanner fertig geschrieben hat (Dateigroesse 2x gleich)."""
    prev_size = -1
    stable_count = 0
    for _ in range(timeout):
        time.sleep(1)
        if not os.path.exists(path):
            return False
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        if size > 0 and size == prev_size:
            stable_count += 1
            if stable_count >= 2:
                return True
        else:
            stable_count = 0
        prev_size = size
    return os.path.exists(path)


class ScanHandler(FileSystemEventHandler):
    def __init__(self, cfg: dict, notify_cb=None):
        self.cfg = cfg
        self._notify_cb = notify_cb

    def on_created(self, event):
        if not event.is_directory:
            self._handle(event.src_path)

    def on_moved(self, event):
        # Einige Scanner legen zuerst Temp-Datei an und benennen sie um
        if not event.is_directory:
            self._handle(event.dest_path)

    def _handle(self, path: str):
        if is_numeric_file(
            os.path.basename(path),
            self.cfg.get("watch_extensions", [".pdf"]),
            self.cfg.get("name_pattern", ""),
        ):
            threading.Thread(
                target=process_file,
                args=(path, self.cfg),
                kwargs={"notify": self._notify_cb},
                daemon=True,
            ).start()


def process_file(path: str, cfg: dict, notify=None) -> bool:
    """
    Komplette Pipeline: Warten -> Lesen -> Benennen -> Verschieben/Umbenennen.
    Gibt True zurueck bei Erfolg.
    """
    global _session_count
    filename = os.path.basename(path)
    original_ext = Path(filename).suffix.lower()
    log.info(f"Neue Datei erkannt: {filename}")

    if not _wait_for_stable(path, cfg.get("stability_timeout", 30)):
        log.warning(f"  Datei verschwunden oder Timeout: {filename}")
        return False

    try:
        text = ocr.extract_text(path, cfg["tesseract_exe"], pages=cfg.get("ocr_max_pages", 2))
        log.info(f"  Text: {len(text)} Zeichen")

        if text:
            model_keys = {
                m: cfg.get(f"{m}_key", "")
                for m in ("claude", "openai", "gemini", "mistral", "groq")
            }
            name = renamer.determine_name(
                text, filename,
                active_model=cfg.get("active_model", "rules"),
                model_keys=model_keys,
                ollama_model=cfg.get("ollama_model", "llama3.2"),
                name_template=cfg.get("name_template", "{DATUM}_{ABSENDER}_{BETREFF}"),
                date_format=cfg.get("date_format", "YYYY-MM-DD"),
                space_replacement=cfg.get("space_replacement", "-"),
                custom_senders=cfg.get("custom_senders", {}),
                custom_doc_types=cfg.get("custom_doc_types", {}),
            )
        else:
            name = f"UNLESBAR_{Path(filename).stem}"
            log.warning("  Kein Text lesbar -> UNLESBAR-Prefix")

        strategy = cfg.get("duplicate_strategy", "suffix")
        target_folder = cfg.get("target_folder", "").strip()
        if target_folder:
            dest = renamer.unique_path(target_folder, name + original_ext, strategy)
            shutil.move(path, dest)
        else:
            src_dir = os.path.dirname(path)
            dest = renamer.unique_path(src_dir, name + original_ext, strategy)
            os.rename(path, dest)

        log.info(f"  OK: {filename}  ->  {os.path.basename(dest)}")

        telemetry.track_rename(cfg.get("active_model", "rules"), success=True)

        with _count_lock:
            _session_count += 1
        with _recent_lock:
            _recent_files.insert(0, os.path.basename(dest))
            del _recent_files[_MAX_RECENT:]

        if notify:
            try:
                notify(os.path.basename(dest))
            except Exception:
                pass

        return True

    except Exception as e:
        log.error(f"  Fehler bei {filename}: {e}")
        telemetry.track_rename("none", success=False)
        return False


class WatcherService:
    def __init__(self, cfg: dict, notify_cb=None):
        self.cfg = cfg
        self._notify_cb = notify_cb
        self._observer: Observer | None = None

    def start(self):
        if self._observer and self._observer.is_alive():
            return
        self._observer = Observer()
        handler = ScanHandler(self.cfg, notify_cb=self._notify_cb)
        self._observer.schedule(handler, self.cfg["source_folder"], recursive=False)
        self._observer.start()
        log.info(f"Ueberwachung gestartet: {self.cfg['source_folder']}")

        # Bestehende Dateien beim Start verarbeiten
        threading.Thread(target=self._process_existing, daemon=True).start()

    def _process_existing(self):
        folder = self.cfg.get("source_folder", "")
        if not folder or not os.path.isdir(folder):
            return
        time.sleep(1)  # Kurz warten bis Observer laeuft
        exts = self.cfg.get("watch_extensions", [".pdf"])
        pattern = self.cfg.get("name_pattern", "")
        found = [
            f for f in os.listdir(folder)
            if is_numeric_file(f, exts, pattern) and os.path.isfile(os.path.join(folder, f))
        ]
        if found:
            log.info(f"  {len(found)} bestehende Datei(en) im Eingangsordner gefunden...")
            for fname in found:
                process_file(os.path.join(folder, fname), self.cfg, notify=self._notify_cb)

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        log.info("Ueberwachung gestoppt.")

    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()

    def restart(self, new_cfg: dict):
        self.stop()
        self.cfg = new_cfg
        if new_cfg.get("source_folder"):
            self.start()
