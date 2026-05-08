"""
@file    main.py
@project Scan Watcher
@company Nova Network GmbH
@date    Mai 2026
@brief   Haupteinstiegspunkt – Single-Instance-Schutz, Logging, First-Run-Setup.
"""

import ctypes
import logging
import logging.handlers
import sys

from . import config, telemetry

APP_VERSION = "1.0.9"


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
        logging.handlers.RotatingFileHandler(
            log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("scan_watcher")


def main():
    _ensure_single_instance()
    cfg = config.load()
    _level = getattr(logging, cfg.get("log_level", "INFO"), logging.INFO)
    logging.getLogger().setLevel(_level)
    log.info("Scan Watcher gestartet (Nova Network)")

    # Einmalige Telemetrie-Einwilligung (DSGVO Opt-in)
    if not cfg.get("telemetry_asked", False):
        cfg = _ask_telemetry_consent(cfg)

    telemetry.track_install(APP_VERSION)

    # Beim ersten Start: Einstellungen oeffnen
    if not cfg["source_folder"]:
        log.info("Kein Eingangsordner konfiguriert – Einstellungen werden geoeffnet.")
        _first_run_setup(cfg)
        return

    from .tray import TrayApp
    app = TrayApp(version=APP_VERSION)
    app.run()


def _ask_telemetry_consent(cfg: dict) -> dict:
    """Zeigt einmaligen DSGVO-Opt-in-Dialog. Gibt aktualisiertes cfg zurueck."""
    import customtkinter as ctk

    consented = [False]

    root = ctk.CTk()
    root.withdraw()

    dlg = ctk.CTkToplevel(root)
    dlg.title("Scan Watcher – Nutzungsstatistiken")
    dlg.resizable(False, False)
    dlg.configure(fg_color="#141420")
    dlg.grab_set()

    ctk.CTkLabel(
        dlg,
        text="Darf Scan Watcher anonyme Nutzungsdaten senden?",
        font=ctk.CTkFont(size=14, weight="bold"),
        wraplength=360,
        anchor="w",
    ).pack(padx=24, pady=(24, 8), fill="x")

    ctk.CTkLabel(
        dlg,
        text=(
            "Wir erfahren:\n"
            "  App-Version, Windows-Build, genutztes KI-Modell,\n"
            "  Anzahl Umbenennungen (Erfolg / Fehler)\n\n"
            "Wir erfahren nicht:\n"
            "  Dateinamen, Dateiinhalte, Benutzername, Hostname, IP-Adresse\n\n"
            "Die Daten helfen uns, Scan Watcher zu verbessern.\n"
            "Einwilligung jederzeit in den Einstellungen widerrufbar."
        ),
        font=ctk.CTkFont(size=11),
        text_color="#aaa",
        justify="left",
        anchor="w",
    ).pack(padx=24, pady=(0, 20), fill="x")

    btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
    btn_row.pack(padx=24, pady=(0, 24), fill="x")

    def on_yes():
        consented[0] = True
        dlg.destroy()

    def on_no():
        dlg.destroy()

    ctk.CTkButton(btn_row, text="Ja, erlauben", width=140, height=36, command=on_yes).pack(
        side="left", padx=(0, 8)
    )
    ctk.CTkButton(
        btn_row, text="Nein danke", width=120, height=36,
        fg_color="transparent", border_width=1, border_color="#444",
        hover_color="#2a2a3a", command=on_no,
    ).pack(side="left")

    w, h = 420, 320
    sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
    dlg.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    root.wait_window(dlg)
    root.destroy()

    cfg["telemetry_enabled"] = consented[0]
    cfg["telemetry_asked"] = True
    config.save(cfg)
    log.info(f"Telemetrie-Einwilligung: {'ja' if consented[0] else 'nein'}")
    return cfg


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
        app = TrayApp(version=APP_VERSION)
        app.run()


if __name__ == "__main__":
    main()
