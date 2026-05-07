"""
@file    tray.py
@project Scan Watcher
@company Nova Network GmbH
@date    Mai 2026
@brief   System-Tray-Icon (pystray) – Statusanzeige, Kontextmenue,
         Windows-Benachrichtigungen und Einstellungs-Dialog.
"""

import logging
import threading
import tkinter as tk
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

from . import config
from .settings_dialog import SettingsDialog
from .watcher import WatcherService, get_session_count

log = logging.getLogger("scan_watcher.tray")


def create_icon_image(running: bool = True) -> Image.Image:
    """Erstellt ein einfaches Icon-Bild (wird ersetzt wenn assets/icon.png vorhanden)."""
    icon_path = Path(__file__).parent.parent / "assets" / "icon.png"
    if icon_path.exists():
        return Image.open(icon_path).resize((64, 64))

    # Fallback: programmatisch generiertes Icon
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = "#22c55e" if running else "#ef4444"
    draw.ellipse([4, 4, 60, 60], fill=color)
    draw.text((18, 18), "SW", fill="white")
    return img


class TrayApp:
    def __init__(self):
        self.cfg = config.load()
        self.watcher = WatcherService(self.cfg, notify_cb=self._notify)
        self._icon: pystray.Icon | None = None

    def run(self):
        if self.cfg["source_folder"]:
            self.watcher.start()

        menu = pystray.Menu(
            pystray.MenuItem("Scan Watcher – Nova Network", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Status", self._show_status),
            pystray.MenuItem("Einstellungen", self._open_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Beenden", self._quit),
        )

        self._icon = pystray.Icon(
            name="ScanWatcher",
            icon=create_icon_image(self.watcher.is_running()),
            title="Scan Watcher",
            menu=menu,
        )
        self._icon.run()

    def _update_icon(self):
        if self._icon:
            self._icon.icon = create_icon_image(self.watcher.is_running())

    def _show_status(self, icon, item):
        status = "Aktiv" if self.watcher.is_running() else "Gestoppt"
        count = get_session_count()
        src = self.cfg.get("source_folder", "(nicht gesetzt)")
        dst = self.cfg.get("target_folder", "") or "(im Eingangsordner)"
        self._tk_messagebox(
            "Scan Watcher – Status",
            f"Status:              {status}\n"
            f"Umbenannt (Session): {count} Datei(en)\n\n"
            f"Eingangsordner: {src}\n"
            f"Ausgangsordner: {dst}"
        )

    def _open_settings(self, icon=None, item=None):
        def run_dialog():
            import customtkinter as ctk
            root = ctk.CTk()
            root.withdraw()
            dlg = SettingsDialog(root, self.cfg, on_save=self._on_settings_saved)
            root.wait_window(dlg)
            root.destroy()

        threading.Thread(target=run_dialog, daemon=True).start()

    def _notify(self, filename: str):
        if self._icon and self.cfg.get("notifications", True):
            try:
                self._icon.notify(filename, "Scan Watcher")
            except Exception:
                pass

    def _on_settings_saved(self, new_cfg: dict):
        log.info("Einstellungen gespeichert – Watcher wird neu gestartet.")
        self.watcher.restart(new_cfg)
        self.cfg = new_cfg
        self._update_icon()

    def _tk_messagebox(self, title: str, message: str):
        def show():
            root = tk.Tk()
            root.withdraw()
            from tkinter import messagebox
            messagebox.showinfo(title, message)
            root.destroy()

        threading.Thread(target=show, daemon=True).start()

    def _quit(self, icon, item):
        self.watcher.stop()
        icon.stop()
