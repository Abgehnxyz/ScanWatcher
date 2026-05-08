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


def get_session_count() -> int:
    return _session_count


def is_numeric_pdf(filename: str) -> bool:
    """Prueft ob Dateiname ausschliesslich aus Ziffern besteht (Scanner-Output)."""
    return Path(filename).stem.isdigit() and filename.lower().endswith(".pdf")


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
        if is_numeric_pdf(os.path.basename(path)):
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
    log.info(f"Neue Datei erkannt: {filename}")

    if not _wait_for_stable(path):
        log.warning(f"  Datei verschwunden oder Timeout: {filename}")
        return False

    try:
        text = ocr.extract_text(path, cfg["tesseract_exe"])
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
            )
        else:
            name = f"UNLESBAR_{Path(filename).stem}"
            log.warning("  Kein Text lesbar -> UNLESBAR-Prefix")

        target_folder = cfg.get("target_folder", "").strip()
        if target_folder:
            dest = renamer.unique_path(target_folder, name + ".pdf")
            shutil.move(path, dest)
        else:
            src_dir = os.path.dirname(path)
            dest = renamer.unique_path(src_dir, name + ".pdf")
            os.rename(path, dest)

        log.info(f"  OK: {filename}  ->  {os.path.basename(dest)}")

        telemetry.track_rename(cfg.get("active_model", "rules"), success=True)

        with _count_lock:
            _session_count += 1

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
        found = [
            f for f in os.listdir(folder)
            if is_numeric_pdf(f) and os.path.isfile(os.path.join(folder, f))
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
