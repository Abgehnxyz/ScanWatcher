"""
Entwicklungs-Helfer: Startet einzelne Komponenten direkt, ohne Installer/Build.
Aufruf: python run_dev.py [dialog|tray|renamer]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def run_dialog():
    """Nur den Einstellungs-Dialog oeffnen (kein Tray, kein Mutex)."""
    from src import config
    from src.settings_dialog import SettingsDialog
    from src.ui import UiThread

    cfg = config.load()
    ui = UiThread(cfg.get("appearance_mode", "dark"))
    ui.start()

    def build(root, finish):
        dlg = SettingsDialog(root, cfg, on_save=lambda c: print("Gespeichert."))
        dlg.bind("<Destroy>", lambda e: e.widget is dlg and finish(None), add="+")

    ui.ask(build)
    ui.stop()


def run_tray():
    """Tray-App starten (mit Mutex-Schutz, wie Produktion)."""
    from src.main import main
    main()


def run_renamer():
    """Template-Engine mit Beispieldaten testen."""
    from src import renamer

    tests = [
        ("{DATUM}_{ABSENDER}_{BETREFF}", "YYYY-MM-DD", "-"),
        ("{DATUM}_{ABSENDER}_{BETREFF}", "DD.MM.YYYY", "-"),
        ("{DATUM}_{ABSENDER}_{BETREFF}", "YYYYMMDD", "_"),
        ("{JAHR}/{MONAT}/{TAG}_{ABSENDER}", "YYYY-MM-DD", "-"),
        ("SCAN_{DATUM}_{ABSENDER}_{BETREFF}", "YYYY-MM-DD", "_"),
    ]

    ocr_text = """
    HUK-COBURG Versicherung
    Datum: 08.05.2026
    Rechnung Nr. RE-99001
    Beitragsrechnung fuer Ihre Kfz-Versicherung
    """

    print("=== Template-Engine Test ===\n")
    for template, date_fmt, space_rep in tests:
        result = renamer.determine_name(
            ocr_text, "20260508001.pdf",
            name_template=template,
            date_format=date_fmt,
            space_replacement=space_rep,
        )
        print(f"Template : {template}")
        print(f"Format   : {date_fmt}  |  Leerzeichen→'{space_rep}'")
        print(f"Ergebnis : {result}.pdf")
        print()


def run_consent():
    """Telemetrie-Opt-in-Dialog anzeigen (setzt telemetry_asked zurueck)."""
    from src import config
    from src.main import _ask_telemetry_consent
    from src.ui import UiThread

    cfg = config.load()
    cfg["telemetry_asked"] = False  # Reset fuer Testlauf
    ui = UiThread(cfg.get("appearance_mode", "dark"))
    ui.start()
    result = _ask_telemetry_consent(ui, cfg)
    ui.stop()
    print(f"Ergebnis: telemetry_enabled={result['telemetry_enabled']}")


MODES = {"dialog": run_dialog, "tray": run_tray, "renamer": run_renamer, "consent": run_consent}

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "dialog"
    if mode not in MODES:
        print(f"Unbekannter Modus '{mode}'. Verfuegbar: {', '.join(MODES)}")
        sys.exit(1)
    MODES[mode]()
