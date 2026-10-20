"""
@file    watcher.py
@project Scan Watcher
@company Nova Network
@date    Mai 2026
@brief   Dateiueberwachung mit watchdog – erkennt neue numerisch benannte PDFs,
         wartet auf stabile Dateigroesse und startet die Verarbeitungs-Pipeline.
         OCR laeuft in einem kleinen Worker-Pool, damit ein Stapel-Scan nicht
         dutzende Tesseract-Prozesse gleichzeitig startet.
"""

import logging
import os
import re
import shutil
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from . import config, ocr, renamer, telemetry

log = logging.getLogger("scan_watcher.watcher")

_OCR_WORKERS = 2

_session_count = 0
_count_lock = threading.Lock()
_recent_files: list[str] = []
_recent_lock = threading.Lock()
_MAX_RECENT = 20

# Dateien, die gerade verarbeitet werden (Event + Startscan, mehrere Profile
# auf demselben Ordner) – jede Datei nur einmal.
_claimed: set[str] = set()
# Zuletzt von uns erzeugte Dateien – deren Events ignorieren (Endlosschleife,
# wenn der neue Name zufaellig wieder zum Namensmuster passt).
_produced: deque[str] = deque(maxlen=200)
_state_lock = threading.Lock()

_executor = ThreadPoolExecutor(max_workers=_OCR_WORKERS, thread_name_prefix="ocr")


def get_session_count() -> int:
    return _session_count


def get_recent_files() -> list[str]:
    with _recent_lock:
        return list(_recent_files)


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def _claim(path: str) -> bool:
    """Datei zur Verarbeitung reservieren. False, wenn schon in Arbeit oder
    von uns selbst erzeugt."""
    key = _norm(path)
    with _state_lock:
        if key in _claimed or key in _produced:
            return False
        _claimed.add(key)
        return True


def _release(path: str) -> None:
    with _state_lock:
        _claimed.discard(_norm(path))


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


def _move(src: str, dest: str, overwrite: bool) -> None:
    """Verschieben/Umbenennen. Ueberschreiben per os.replace – os.rename wirft
    unter Windows FileExistsError, wenn das Ziel existiert."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        if overwrite:
            os.replace(src, dest)
        else:
            os.rename(src, dest)
    except OSError:
        if os.path.exists(dest) and not overwrite:
            raise
        shutil.move(src, dest)   # anderes Laufwerk / Netzlaufwerk


def ai_options(cfg: dict) -> dict:
    """KI-Einstellungen aus der Config fuer renamer.determine_name()."""
    return {
        "active_model": cfg.get("active_model", "rules"),
        "model_keys": {m: config.get_model_key(m) for m in config.KEY_MODELS},
        "model_ids": cfg.get("model_ids", {}),
        "ollama_model": cfg.get("ollama_model", ""),
        "ollama_url": cfg.get("ollama_url", ""),
        "custom_base_url": cfg.get("custom_base_url", ""),
    }


def _dest_path(folder: str, name: str, ext: str, strategy: str) -> str:
    """Zielpfad aus relativem Namen (ggf. mit Unterordnern "2026/05/…")."""
    parts = name.split("/")
    subdir = os.path.join(folder, *parts[:-1])
    return renamer.unique_path(subdir, parts[-1] + ext, strategy)


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
            submit(path, self.cfg, self._notify_cb)


def submit(path: str, cfg: dict, notify=None) -> bool:
    """Datei zur Verarbeitung einreihen. Stabilitaets-Warten laeuft in einem
    leichten Thread, OCR/Umbenennen im Worker-Pool."""
    if not _claim(path):
        return False

    def wait_then_queue():
        if not _wait_for_stable(path, cfg.get("stability_timeout", 30)):
            log.warning(f"  Datei verschwunden oder Timeout: {os.path.basename(path)}")
            _release(path)
            return
        _executor.submit(_process_claimed, path, cfg, notify)

    threading.Thread(target=wait_then_queue, daemon=True).start()
    return True


def _process_claimed(path: str, cfg: dict, notify=None) -> bool:
    try:
        return _process(path, cfg, notify)
    finally:
        _release(path)


def process_file(path: str, cfg: dict, notify=None) -> bool:
    """
    Komplette Pipeline synchron: Warten -> Lesen -> Benennen -> Verschieben.
    Gibt True zurueck bei Erfolg.
    """
    if not _claim(path):
        return False
    try:
        if not _wait_for_stable(path, cfg.get("stability_timeout", 30)):
            log.warning(f"  Datei verschwunden oder Timeout: {os.path.basename(path)}")
            return False
        return _process(path, cfg, notify)
    finally:
        _release(path)


def _process(path: str, cfg: dict, notify=None) -> bool:
    global _session_count
    filename = os.path.basename(path)
    original_ext = Path(filename).suffix.lower()
    log.info(f"Neue Datei erkannt: {filename}")
    used = cfg.get("active_model", "rules")

    try:
        ocr_result = ocr.extract_text_with_confidence(
            path, cfg["tesseract_exe"], pages=cfg.get("ocr_max_pages", 2)
        )
        text = ocr_result.text
        log.info(f"  Text: {len(text)} Zeichen, Konfidenz: {ocr_result.confidence:.0f}%")

        if text:
            name, used = renamer.determine_name_with_source(
                text, filename,
                name_template=cfg.get("name_template", "{DATUM}_{ABSENDER}_{BETREFF}"),
                date_format=cfg.get("date_format", "YYYY-MM-DD"),
                space_replacement=cfg.get("space_replacement", "-"),
                custom_senders=cfg.get("custom_senders", {}),
                custom_doc_types=cfg.get("custom_doc_types", {}),
                **ai_options(cfg),
            )
            if ocr.needs_review(ocr_result):
                # Prefix gehoert vor den Dateinamen, nicht vor einen Unterordner
                head, _, tail = name.rpartition("/")
                name = f"{head}/PRUEFEN_{tail}" if head else f"PRUEFEN_{tail}"
            unreadable = False
        else:
            name = f"UNLESBAR_{Path(filename).stem}"
            unreadable = True
            log.warning("  Kein Text lesbar -> UNLESBAR-Prefix")

        strategy = cfg.get("duplicate_strategy", "suffix")
        unlesbar_dir = cfg.get("unlesbar_folder", "").strip()
        target_folder = cfg.get("target_folder", "").strip()

        if unreadable and unlesbar_dir:
            folder = unlesbar_dir
        elif target_folder:
            folder = target_folder
        else:
            folder = os.path.dirname(path)

        dest = _dest_path(folder, name, original_ext, strategy)
        with _state_lock:
            _produced.append(_norm(dest))
        _move(path, dest, overwrite=(strategy == "overwrite"))

        shown = os.path.relpath(dest, folder)
        log.info(f"  OK: {filename}  ->  {shown}")

        telemetry.track_rename(used, success=True)

        with _count_lock:
            _session_count += 1
        with _recent_lock:
            _recent_files.insert(0, shown)
            del _recent_files[_MAX_RECENT:]

        if notify:
            try:
                notify(shown)
            except Exception:
                pass

        return True

    except Exception as e:
        log.error(f"  Fehler bei {filename}: {e}")
        telemetry.track_rename(used, success=False)
        return False


class WatcherService:
    def __init__(self, cfg: dict, notify_cb=None):
        self.cfg = cfg
        self._notify_cb = notify_cb
        self._observer: Observer | None = None

    def start(self):
        if self._observer and self._observer.is_alive():
            return
        src = self.cfg["source_folder"]
        if not os.path.isdir(src):
            log.error(f"Eingangsordner nicht gefunden: {src}")
            return
        if not os.access(src, os.R_OK | os.W_OK):
            log.error(f"Keine Lese-/Schreibrechte fuer: {src}")
            return
        tgt = self.cfg.get("target_folder", "").strip()
        if tgt and not os.path.isdir(tgt):
            log.error(f"Ausgangsordner nicht gefunden: {tgt}")
            return
        self._observer = Observer()
        handler = ScanHandler(self.cfg, notify_cb=self._notify_cb)
        self._observer.schedule(handler, src, recursive=False)
        self._observer.start()
        log.info(f"Ueberwachung gestartet: {src}")

        # Bestehende Dateien beim Start verarbeiten
        threading.Thread(target=self._process_existing, daemon=True).start()

    def _process_existing(self):
        folder = self.cfg.get("source_folder", "")
        if not folder or not os.path.isdir(folder):
            return
        exts = self.cfg.get("watch_extensions", [".pdf"])
        pattern = self.cfg.get("name_pattern", "")
        found = [
            f for f in os.listdir(folder)
            if is_numeric_file(f, exts, pattern) and os.path.isfile(os.path.join(folder, f))
        ]
        if found:
            log.info(f"  {len(found)} bestehende Datei(en) im Eingangsordner gefunden...")
            for fname in found:
                submit(os.path.join(folder, fname), self.cfg, self._notify_cb)

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        log.info("Ueberwachung gestoppt.")

    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()
