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
from datetime import date
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

from . import config, telemetry
from .settings_dialog import SettingsDialog
from .watcher import WatcherService, get_session_count, get_recent_files

log = logging.getLogger("scan_watcher.tray")

_HEARTBEAT_INTERVAL_DAYS = 7


def create_icon_image(running: bool = True) -> Image.Image:
    """Erstellt ein einfaches Icon-Bild (wird ersetzt wenn assets/icon.png vorhanden)."""
    icon_path = Path(__file__).parent.parent / "assets" / "icon.png"
    if icon_path.exists():
        return Image.open(icon_path).resize((64, 64))

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = "#22c55e" if running else "#ef4444"
    draw.ellipse([4, 4, 60, 60], fill=color)
    draw.text((18, 18), "SW", fill="white")
    return img


class TrayApp:
    def __init__(self, version: str = "0.0.0"):
        self.version = version
        self.cfg = config.load()
        self._watchers: list[WatcherService] = []
        self._icon: pystray.Icon | None = None
        self._heartbeat_timer: threading.Timer | None = None

    def _start_watchers(self):
        for w in self._watchers:
            w.stop()
        self._watchers = []
        for profile in self.cfg.get("folder_profiles", []):
            src = profile.get("source", "").strip()
            if src:
                profile_cfg = {**self.cfg, "source_folder": src,
                               "target_folder": profile.get("target", "")}
                w = WatcherService(profile_cfg, notify_cb=self._notify)
                self._watchers.append(w)
                w.start()

    def _any_running(self) -> bool:
        return any(w.is_running() for w in self._watchers)

    def run(self):
        self._start_watchers()
        self._heartbeat_check()

        menu = pystray.Menu(
            pystray.MenuItem("Scan Watcher – Nova Network", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Status", self._show_status),
            pystray.MenuItem(
                "Zuletzt verarbeitet",
                pystray.Menu(lambda: self._recent_menu_items()),
            ),
            pystray.MenuItem("Verarbeitete Dateien …", self._show_log_window),
            pystray.MenuItem("Einstellungen", self._open_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Beenden", self._quit),
        )

        self._icon = pystray.Icon(
            name="ScanWatcher",
            icon=create_icon_image(self._any_running()),
            title="Scan Watcher",
            menu=menu,
        )
        self._icon.run()

    def _heartbeat_check(self):
        """Sendet Heartbeat wenn 7 Tage seit letztem vergangen. Plant naechsten Check."""
        try:
            last_str = self.cfg.get("last_heartbeat", "")
            last = date.fromisoformat(last_str) if last_str else None
            if last is None or (date.today() - last).days >= _HEARTBEAT_INTERVAL_DAYS:
                telemetry.track_heartbeat(self.version, get_session_count())
                self.cfg["last_heartbeat"] = date.today().isoformat()
                config.save(self.cfg)
                log.debug("Heartbeat gesendet.")
        except Exception as e:
            log.debug(f"Heartbeat: {e}")

        # Naechsten Check in 24h einplanen (faengt auch lange laufende Instanzen ab)
        self._heartbeat_timer = threading.Timer(24 * 3600, self._heartbeat_check)
        self._heartbeat_timer.daemon = True
        self._heartbeat_timer.start()

    def _update_icon(self):
        if self._icon:
            self._icon.icon = create_icon_image(self._any_running())

    def _show_status(self, icon, item):
        count = get_session_count()
        running = sum(1 for w in self._watchers if w.is_running())
        profiles = self.cfg.get("folder_profiles", [])
        lines = f"Umbenannt (Session): {count} Datei(en)\n"
        lines += f"Aktive Watcher:      {running} / {len(profiles)}\n"
        for p in profiles:
            src = p.get("source", "(nicht gesetzt)")
            tgt = p.get("target", "") or "(im Eingangsordner)"
            name = p.get("name", "Profil")
            lines += f"\n{name}:\n  Quelle: {src}\n  Ziel:   {tgt}"
        self._tk_messagebox("Scan Watcher – Status", lines)

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
        self.cfg = new_cfg
        self._start_watchers()
        self._update_icon()

    def _recent_menu_items(self):
        recent = get_recent_files()[:5]
        if not recent:
            return [pystray.MenuItem("(noch keine Dateien)", None, enabled=False)]
        return [pystray.MenuItem(name, None, enabled=False) for name in recent]

    def _show_log_window(self, icon=None, item=None):
        def run():
            import customtkinter as ctk
            root = ctk.CTk()
            root.title("Scan Watcher – Verarbeitete Dateien")
            root.geometry("600x400")
            root.configure(fg_color="#141420")

            ctk.CTkLabel(
                root,
                text="Verarbeitete Dateien (diese Session)",
                font=ctk.CTkFont(size=13, weight="bold"),
            ).pack(padx=20, pady=(16, 8))

            box = ctk.CTkScrollableFrame(root, fg_color="#1e1e2e", corner_radius=8)
            box.pack(fill="both", expand=True, padx=20, pady=(0, 16))

            files = get_recent_files()
            if files:
                for i, name in enumerate(files, 1):
                    ctk.CTkLabel(
                        box,
                        text=f"{i:>3}.  {name}",
                        font=ctk.CTkFont(size=11, family="Courier New"),
                        text_color="#88ccff",
                        anchor="w",
                    ).pack(fill="x", padx=12, pady=2)
            else:
                ctk.CTkLabel(
                    box, text="Noch keine Dateien verarbeitet.",
                    text_color="#666", anchor="w",
                ).pack(padx=12, pady=8)

            ctk.CTkButton(root, text="Schließen", width=100, command=root.destroy).pack(pady=(0, 16))
            root.mainloop()

        threading.Thread(target=run, daemon=True).start()

    def _tk_messagebox(self, title: str, message: str):
        def show():
            root = tk.Tk()
            root.withdraw()
            from tkinter import messagebox
            messagebox.showinfo(title, message)
            root.destroy()

        threading.Thread(target=show, daemon=True).start()

    def _quit(self, icon, item):
        if self._heartbeat_timer:
            self._heartbeat_timer.cancel()
        for w in self._watchers:
            w.stop()
        icon.stop()
