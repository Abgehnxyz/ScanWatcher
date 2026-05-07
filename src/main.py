"""
@file    main.py
@project Scan Watcher
@company Nova Network GmbH
@date    Mai 2026
@brief   Haupteinstiegspunkt – Single-Instance-Schutz, Logging, First-Run-Setup.
"""

import ctypes
import logging
import sys
from pathlib import Path

# Logging konfigurieren
from . import config


def _ensure_single_instance():
    """Verhindert mehrfache Instanzen via Windows-Mutex."""
    mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "ScanWatcher_Nova_Network_SingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)

log_path = config.get_log_path()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("scan_watcher")


def main():
    _ensure_single_instance()
    log.info("Scan Watcher gestartet (Nova Network)")
    cfg = config.load()

    # Beim ersten Start: Einstellungen oeffnen
    if not cfg["source_folder"]:
        log.info("Kein Eingangsordner konfiguriert – Einstellungen werden geoeffnet.")
        _first_run_setup(cfg)
        return

    # Tray-App starten
    from .tray import TrayApp
    app = TrayApp()
    app.run()


def _first_run_setup(cfg: dict):
    """Beim ersten Start Einstellungs-Dialog zeigen."""
    import customtkinter as ctk
    from .settings_dialog import SettingsDialog
    from .tray import TrayApp

    root = ctk.CTk()
    root.withdraw()

    saved = []

    def on_save(new_cfg):
        saved.append(new_cfg)

    dlg = SettingsDialog(root, cfg, on_save=on_save)
    root.wait_window(dlg)
    root.destroy()

    if saved:
        app = TrayApp()
        app.run()


if __name__ == "__main__":
    main()
