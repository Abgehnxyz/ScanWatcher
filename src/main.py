"""
@file    main.py
@project Scan Watcher
@company Nova Network
@date    Mai 2026
@brief   Haupteinstiegspunkt – Single-Instance-Schutz, Logging, First-Run-Setup.
"""

import ctypes
import logging
import logging.handlers
import os
import sys
import traceback

from . import __version__ as APP_VERSION
from . import config, telemetry, theme
from .ui import UiThread


def _ensure_single_instance():
    """Verhindert mehrfache Instanzen via Windows-Mutex."""
    ctypes.windll.kernel32.CreateMutexW(None, True, "ScanWatcher_Nova_Network_SingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)


_handlers: list[logging.Handler] = [
    logging.handlers.RotatingFileHandler(
        config.get_log_path(), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    ),
]
if sys.stdout is not None:   # im --windowed-Build gibt es keine Konsole
    _handlers.append(logging.StreamHandler(sys.stdout))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    handlers=_handlers,
)
log = logging.getLogger("scan_watcher")


def _install_crash_handler():
    """Schreibt unbehandelte Exceptions in eine separate Crash-Log-Datei."""
    crash_log = config.CONFIG_DIR / "crash.log"

    def handle(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        log.critical(f"Unbehandelte Exception:\n{text}")
        try:
            config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(crash_log, "a", encoding="utf-8") as f:
                from datetime import datetime
                f.write(f"\n--- {datetime.now().isoformat()} ---\n{text}")
        except Exception:
            pass

    sys.excepthook = handle
    # Auch Exceptions in Hintergrund-Threads protokollieren
    import threading
    threading.excepthook = lambda args: handle(args.exc_type, args.exc_value, args.exc_traceback)


def main():
    _ensure_single_instance()
    _install_crash_handler()
    cfg = config.load()
    _level = getattr(logging, cfg.get("log_level", "INFO"), logging.INFO)
    logging.getLogger().setLevel(_level)
    log.info(f"Scan Watcher {APP_VERSION} gestartet (Nova Network)")

    ui = UiThread(cfg.get("appearance_mode", "dark"))
    ui.start()

    # Einmalige Telemetrie-Einwilligung (DSGVO Opt-in)
    if not cfg.get("telemetry_asked", False):
        cfg = _ask_telemetry_consent(ui, cfg)

    telemetry.configure(cfg.get("telemetry_enabled", False))
    telemetry.track_install(APP_VERSION, cfg)

    # Beim ersten Start: Einstellungen oeffnen
    profiles = cfg.get("folder_profiles", [])
    if not profiles or not profiles[0].get("source"):
        log.info("Kein Eingangsordner konfiguriert – Einstellungen werden geoeffnet.")
        if not _first_run_setup(ui, cfg):
            _exit(ui)

    from .tray import TrayApp
    TrayApp(version=APP_VERSION, ui=ui).run()
    _exit(ui)


def _exit(ui: UiThread) -> None:
    """Sauber beenden. Der Tcl-Interpreter gehoert dem UI-Thread – raeumt Python
    ihn beim Herunterfahren im Hauptthread ab, bricht Tcl mit
    "Tcl_AsyncDelete: async handler deleted by the wrong thread" ab."""
    ui.stop()
    log.info("Scan Watcher beendet.")
    logging.shutdown()
    os._exit(0)


def _ask_telemetry_consent(ui: UiThread, cfg: dict) -> dict:
    """Zeigt einmaligen DSGVO-Opt-in-Dialog. Gibt aktualisiertes cfg zurueck."""

    def build(root, finish):
        import customtkinter as ctk

        dlg = ctk.CTkToplevel(root)
        theme.prepare_window(dlg, "Scan Watcher – Nutzungsstatistiken")
        dlg.resizable(False, False)

        def close(value: bool):
            dlg.destroy()
            finish(value)

        dlg.protocol("WM_DELETE_WINDOW", lambda: close(False))

        ctk.CTkLabel(
            dlg,
            text="Darf Scan Watcher anonyme Nutzungsdaten senden?",
            font=ctk.CTkFont(size=14, weight="bold"),
            wraplength=380,
            anchor="w",
        ).pack(padx=24, pady=(24, 8), fill="x")

        ctk.CTkLabel(
            dlg,
            text=(
                "Wir erfahren:\n"
                "  App-Version, Windows-Build, genutztes KI-Modell,\n"
                "  Anzahl Umbenennungen (Erfolg / Fehler)\n\n"
                "Wir erfahren nicht:\n"
                "  Dateinamen, Dateiinhalte, Benutzername, Hostname\n\n"
                "Mit Zustimmung ruft Scan Watcher außerdem gelegentlich\n"
                "Hinweise (z. B. zu wichtigen Fehlerbehebungen) von\n"
                "unserem Server ab. IP-Adressen speichern wir nicht.\n\n"
                "Einwilligung jederzeit in den Einstellungen widerrufbar."
            ),
            font=ctk.CTkFont(size=11),
            text_color=theme.MUTED,
            justify="left",
            anchor="w",
        ).pack(padx=24, pady=(0, 20), fill="x")

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(padx=24, pady=(0, 24), fill="x")

        ctk.CTkButton(btn_row, text="Ja, erlauben", width=140, height=36,
                      command=lambda: close(True)).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_row, text="Nein danke", width=120, height=36,
            fg_color="transparent", border_width=1, border_color=theme.BORDER,
            hover_color=theme.DIVIDER, text_color=theme.TEXT,
            command=lambda: close(False),
        ).pack(side="left")

        w, h = 440, 400
        sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
        dlg.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        dlg.grab_set()

    consented = bool(ui.ask(build))
    cfg["telemetry_enabled"] = consented
    cfg["telemetry_asked"] = True
    config.save(cfg)
    log.info(f"Telemetrie-Einwilligung: {'ja' if consented else 'nein'}")
    return cfg


def _first_run_setup(ui: UiThread, cfg: dict) -> dict | None:
    """Beim ersten Start Einstellungs-Dialog zeigen. None = abgebrochen."""
    from .settings_dialog import SettingsDialog

    def build(root, finish):
        saved: list[dict] = []
        dlg = SettingsDialog(root, cfg, on_save=saved.append, version=APP_VERSION)
        dlg.bind("<Destroy>", lambda e: e.widget is dlg and finish(saved[0] if saved else None),
                 add="+")

    return ui.ask(build)


if __name__ == "__main__":
    main()
