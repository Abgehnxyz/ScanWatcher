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

from . import config, telemetry, updater
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
        updater.check_async(
            self.version,
            self.cfg.get("update_channel", "stable"),
            self._on_update_available,
            enabled=self.cfg.get("update_check_enabled", True),
        )
        updater.check_motd_async(
            self.cfg.get("last_motd_id", ""),
            self._on_motd,
        )

        menu = pystray.Menu(
            pystray.MenuItem("Scan Watcher – Nova Network", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Status", self._show_status),
            pystray.MenuItem(
                "Zuletzt verarbeitet",
                pystray.Menu(lambda: self._recent_menu_items()),
            ),
            pystray.MenuItem("Verarbeitete Dateien …", self._show_log_window),
            pystray.MenuItem("Mini-Status", self._show_mini_status),
            pystray.MenuItem("Einstellungen", self._open_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Über Scan Watcher", self._show_about),
            pystray.MenuItem("☕ Scan Watcher unterstützen", self._open_kofi),
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

    def _show_mini_status(self, icon=None, item=None):
        def run():
            import customtkinter as ctk
            root = ctk.CTk()
            root.title("Scan Watcher")
            root.geometry("300x110+20+20")
            root.attributes("-topmost", True)
            root.resizable(False, False)
            root.configure(fg_color="#141420")

            top = ctk.CTkFrame(root, fg_color="transparent")
            top.pack(fill="x", padx=14, pady=(10, 4))

            dot = ctk.CTkLabel(top, text="●", width=18,
                               font=ctk.CTkFont(size=14))
            dot.pack(side="left")
            status_lbl = ctk.CTkLabel(top, text="",
                                      font=ctk.CTkFont(size=12, weight="bold"))
            status_lbl.pack(side="left", padx=(4, 12))
            count_lbl = ctk.CTkLabel(top, text="",
                                     font=ctk.CTkFont(size=11), text_color="#888")
            count_lbl.pack(side="left")

            last_lbl = ctk.CTkLabel(root, text="",
                                    font=ctk.CTkFont(size=10, family="Courier New"),
                                    text_color="#4488cc", anchor="w")
            last_lbl.pack(fill="x", padx=14)

            ctk.CTkButton(root, text="Schließen", height=28,
                          command=root.destroy).pack(pady=(8, 0))

            def refresh():
                running = self._any_running()
                dot.configure(text_color="#22c55e" if running else "#ef4444")
                status_lbl.configure(text="Aktiv" if running else "Gestoppt")
                count_lbl.configure(text=f"{get_session_count()} Datei(en)")
                recent = get_recent_files()
                last_lbl.configure(text=recent[0] if recent else "–")
                root.after(2000, refresh)

            refresh()
            root.mainloop()

        threading.Thread(target=run, daemon=True).start()

    def _on_update_available(self, release: dict):
        tag = release.get("tag_name", "?")
        if self._icon and self.cfg.get("notifications", True):
            try:
                self._icon.notify(
                    f"Version {tag} verfügbar – Klicke für Details.",
                    "Scan Watcher – Update",
                )
            except Exception:
                pass
        threading.Thread(
            target=self._show_update_dialog, args=(release,), daemon=True,
        ).start()

    def _show_update_dialog(self, release: dict):
        import customtkinter as ctk
        tag = release.get("tag_name", "?")
        changelog = release.get("body", "(Kein Changelog verfügbar)")
        html_url  = release.get("html_url", updater._RELEASES_URL)

        root = ctk.CTk()
        root.title(f"Update verfügbar – {tag}")
        root.geometry("500x420")
        root.configure(fg_color="#141420")
        root.attributes("-topmost", True)

        ctk.CTkLabel(root, text=f"Neue Version {tag} verfügbar!",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(padx=20, pady=(16, 4))

        ctk.CTkLabel(root, text="Änderungen:", font=ctk.CTkFont(size=11),
                     anchor="w").pack(fill="x", padx=20)
        box = ctk.CTkScrollableFrame(root, fg_color="#1e1e2e", corner_radius=8, height=180)
        box.pack(fill="x", padx=20, pady=(4, 12))
        ctk.CTkLabel(box, text=changelog, font=ctk.CTkFont(size=10),
                     text_color="#ccc", anchor="w", justify="left",
                     wraplength=440).pack(padx=8, pady=8, fill="x")

        progress_var = ctk.StringVar(value="")
        progress_lbl = ctk.CTkLabel(root, textvariable=progress_var,
                                    font=ctk.CTkFont(size=10), text_color="#888")
        progress_lbl.pack(padx=20)

        bar = ctk.CTkProgressBar(root, width=460)
        bar.set(0)
        bar.pack(padx=20, pady=(4, 8))

        btn_row = ctk.CTkFrame(root, fg_color="transparent")
        btn_row.pack(padx=20, pady=(0, 16), fill="x")

        def on_install():
            install_btn.configure(state="disabled", text="Lade herunter…")

            def on_progress(done, total):
                if total:
                    bar.set(done / total)
                    progress_var.set(f"{done // 1024} / {total // 1024} KB")
                else:
                    progress_var.set(f"{done // 1024} KB")

            def on_done(path, error):
                if error:
                    progress_var.set(f"Fehler: {error}")
                    install_btn.configure(state="normal", text="Nochmal versuchen")
                    return
                progress_var.set("Download abgeschlossen – Installer wird gestartet…")
                root.after(800, lambda: updater.run_installer_and_quit(path))

            updater.download_installer(release, on_progress, on_done)

        install_btn = ctk.CTkButton(btn_row, text="Jetzt installieren",
                                    width=160, height=36, command=on_install)
        install_btn.pack(side="left")

        ctk.CTkButton(btn_row, text="Zur Download-Seite", width=150, height=36,
                      fg_color="transparent", border_width=1, border_color="#444",
                      command=lambda: __import__("webbrowser").open(html_url),
                      ).pack(side="left", padx=(8, 0))

        ctk.CTkButton(btn_row, text="Später", width=80, height=36,
                      fg_color="transparent", command=root.destroy,
                      ).pack(side="right")

        root.mainloop()

    def _on_motd(self, motd_id: str, message: str):
        if self._icon and self.cfg.get("notifications", True):
            try:
                self._icon.notify(message, "Scan Watcher")
            except Exception:
                pass
        self.cfg["last_motd_id"] = motd_id
        config.save(self.cfg)

    def _show_about(self, icon=None, item=None):
        def run():
            import customtkinter as ctk
            import webbrowser
            root = ctk.CTk()
            root.title("Über Scan Watcher")
            root.geometry("380x300")
            root.resizable(False, False)
            root.configure(fg_color="#141420")
            root.attributes("-topmost", True)

            icon_path = Path(__file__).parent.parent / "assets" / "icon.png"
            if icon_path.exists():
                try:
                    from PIL import ImageTk
                    img = ImageTk.PhotoImage(
                        file=str(icon_path), master=root
                    )
                    ctk.CTkLabel(root, image=img, text="").pack(pady=(18, 4))
                    root._img_ref = img
                except Exception:
                    pass

            ctk.CTkLabel(
                root, text=f"Scan Watcher  v{self.version}",
                font=ctk.CTkFont(size=16, weight="bold"),
            ).pack(pady=(4, 2))
            ctk.CTkLabel(
                root, text="Nova Network  |  Lizenz: MIT",
                font=ctk.CTkFont(size=11), text_color="#888",
            ).pack()

            sep = ctk.CTkFrame(root, height=1, fg_color="#2a2a3a")
            sep.pack(fill="x", padx=24, pady=12)

            btn_row = ctk.CTkFrame(root, fg_color="transparent")
            btn_row.pack(padx=24, pady=(0, 8))

            ctk.CTkButton(
                btn_row, text="GitHub", width=110, height=32,
                fg_color="transparent", border_width=1, border_color="#444",
                command=lambda: webbrowser.open(
                    "https://github.com/Abgehnxyz/ScanWatcher"),
            ).pack(side="left", padx=(0, 8))

            ctk.CTkButton(
                btn_row, text="☕ Ko-fi", width=120, height=32,
                fg_color="#29abe0", hover_color="#1a8fbf",
                command=lambda: webbrowser.open(
                    "https://ko-fi.com/novanetwork"),
            ).pack(side="left")

            ctk.CTkButton(
                root, text="Schließen", width=100, height=32,
                command=root.destroy,
            ).pack(pady=(4, 16))

            root.mainloop()

        threading.Thread(target=run, daemon=True).start()

    def _open_kofi(self, icon=None, item=None):
        import webbrowser
        webbrowser.open("https://ko-fi.com/novanetwork")

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
