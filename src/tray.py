"""
@file    tray.py
@project Scan Watcher
@company Nova Network
@date    Mai 2026
@brief   System-Tray-Icon (pystray) – Statusanzeige, Kontextmenue,
         Windows-Benachrichtigungen und Fenster. Alle Fenster laufen im
         gemeinsamen UI-Thread (siehe ui.py); pystray laeuft im Hauptthread.
"""

import logging
import threading
import webbrowser
from datetime import date

import pystray
from PIL import Image, ImageDraw

from . import config, telemetry, theme, updater
from .settings_dialog import SettingsDialog
from .ui import UiThread
from .watcher import WatcherService, get_recent_files, get_session_count

log = logging.getLogger("scan_watcher.tray")

_HEARTBEAT_INTERVAL_DAYS = 7
_KOFI_URL = "https://ko-fi.com/novanetwork"


def create_icon_image(running: bool = True) -> Image.Image:
    """Erstellt ein einfaches Icon-Bild (wird ersetzt wenn assets/icon.png vorhanden)."""
    icon_path = theme.ASSETS / "icon.png"
    if icon_path.exists():
        return Image.open(icon_path).resize((64, 64))

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = theme.GREEN_DOT if running else theme.RED_DOT
    draw.ellipse([4, 4, 60, 60], fill=color)
    draw.text((18, 18), "SW", fill="white")
    return img


def _icon_image(size: int):
    import customtkinter as ctk
    path = theme.ASSETS / "icon.png"
    if not path.exists():
        return None
    return ctk.CTkImage(light_image=Image.open(path), size=(size, size))


class TrayApp:
    def __init__(self, version: str = "0.0.0", ui: UiThread | None = None):
        self.version = version
        self.cfg = config.load()
        self._ui = ui or UiThread(self.cfg.get("appearance_mode", "dark"))
        self._watchers: list[WatcherService] = []
        self._icon: pystray.Icon | None = None
        self._heartbeat_timer: threading.Timer | None = None
        # Offene Fenster (nur im UI-Thread anfassen)
        self._windows: dict[str, object] = {}

    # ------------------------------------------------------------ Watcher

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

    # ------------------------------------------------------------ Start

    def run(self):
        if self._ui.root is None:
            self._ui.start()
        self._start_watchers()
        self._heartbeat_check()
        updater.check_async(
            self.version,
            self.cfg.get("update_channel", "stable"),
            self._on_update_available,
            enabled=self.cfg.get("update_check_enabled", True),
        )
        # Hinweise vom Nova-Network-Server nur mit Einwilligung abrufen –
        # jede Anfrage dorthin uebermittelt die IP-Adresse.
        if self.cfg.get("telemetry_enabled", False):
            updater.check_motd_async(self.cfg.get("last_motd_id", ""), self._on_motd)

        menu = pystray.Menu(
            pystray.MenuItem("Scan Watcher – Nova Network", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Scan Watcher öffnen", self._on_menu(self._show_main_window), default=True),
            pystray.MenuItem("Mini-Status", self._on_menu(self._show_mini_status)),
            pystray.MenuItem(
                "Zuletzt verarbeitet",
                pystray.Menu(lambda: self._recent_menu_items()),
            ),
            pystray.MenuItem("Verarbeitete Dateien …", self._on_menu(self._show_log_window)),
            pystray.MenuItem("Einstellungen", self._on_menu(self._open_settings)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("☕ Unterstützen", lambda icon, item: webbrowser.open(_KOFI_URL)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Beenden", lambda icon, item: self._quit()),
        )

        self._icon = pystray.Icon(
            name="ScanWatcher",
            icon=create_icon_image(self._any_running()),
            title=f"Scan Watcher v{self.version}",
            menu=menu,
        )
        self._icon.run()

    def _on_menu(self, ui_fn):
        """Menue-Callback (pystray-Thread) → Fensterfunktion im UI-Thread."""
        return lambda icon=None, item=None: self._ui.submit(ui_fn)

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

    def _notify(self, filename: str):
        if self._icon and self.cfg.get("notifications", True):
            try:
                self._icon.notify(filename, "Scan Watcher")
            except Exception:
                pass

    # ------------------------------------------------------------ Fenster-Helfer

    def _existing(self, key: str):
        """Offenes Fenster nach vorn holen. True, wenn es schon existiert."""
        win = self._windows.get(key)
        if win is not None and win.winfo_exists():
            theme.bring_to_front(win)
            return True
        self._windows.pop(key, None)
        return False

    def _new_window(self, key: str, title: str, geometry: str):
        import customtkinter as ctk
        win = ctk.CTkToplevel(self._ui.root)
        win.geometry(geometry)
        theme.prepare_window(win, title)
        self._windows[key] = win
        return win

    # ------------------------------------------------------------ Einstellungen

    def _open_settings(self):
        if self._existing("settings"):
            return
        dlg = SettingsDialog(self._ui.root, self.cfg, on_save=self._on_settings_saved,
                             version=self.version)
        self._windows["settings"] = dlg

    def _on_settings_saved(self, new_cfg: dict):
        log.info("Einstellungen gespeichert – Watcher wird neu gestartet.")
        self.cfg = new_cfg
        telemetry.configure(new_cfg.get("telemetry_enabled", False))
        theme.apply_appearance(new_cfg.get("appearance_mode", "dark"))
        self._start_watchers()
        self._update_icon()

    # ------------------------------------------------------------ Mini-Status

    def _show_mini_status(self):
        import customtkinter as ctk
        if self._existing("mini"):
            return
        win = self._new_window("mini", "Scan Watcher", "300x110+20+20")
        win.attributes("-topmost", True)
        win.resizable(False, False)

        top = ctk.CTkFrame(win, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(10, 4))

        dot = ctk.CTkLabel(top, text="●", width=18, font=ctk.CTkFont(size=14))
        dot.pack(side="left")
        status_lbl = ctk.CTkLabel(top, text="", font=ctk.CTkFont(size=12, weight="bold"))
        status_lbl.pack(side="left", padx=(4, 12))
        count_lbl = ctk.CTkLabel(top, text="", font=ctk.CTkFont(size=11), text_color=theme.MUTED)
        count_lbl.pack(side="left")

        last_lbl = ctk.CTkLabel(win, text="", font=ctk.CTkFont(size=10, family="Courier New"),
                                text_color=theme.INFO, anchor="w")
        last_lbl.pack(fill="x", padx=14)

        ctk.CTkButton(win, text="Schließen", height=28, command=win.destroy).pack(pady=(8, 0))

        def refresh():
            if not win.winfo_exists():
                return
            running = self._any_running()
            dot.configure(text_color=theme.GREEN_DOT if running else theme.RED_DOT)
            status_lbl.configure(text="Aktiv" if running else "Gestoppt")
            count_lbl.configure(text=f"{get_session_count()} Datei(en)")
            recent = get_recent_files()
            last_lbl.configure(text=recent[0] if recent else "–")
            win.after(2000, refresh)

        refresh()

    # ------------------------------------------------------------ Updates

    def _on_update_available(self, release: dict):
        tag = release.get("tag_name", "?")
        if self._icon and self.cfg.get("notifications", True):
            try:
                self._icon.notify(f"Version {tag} verfügbar.", "Scan Watcher – Update")
            except Exception:
                pass
        self._ui.submit(lambda: self._show_update_dialog(release))

    def _show_update_dialog(self, release: dict):
        import customtkinter as ctk
        if self._existing("update"):
            return
        tag = release.get("tag_name", "?")
        changelog = release.get("body") or "(Kein Changelog verfügbar)"
        html_url = release.get("html_url", updater._RELEASES_URL)

        win = self._new_window("update", f"Update verfügbar – {tag}", "500x420")

        ctk.CTkLabel(win, text=f"Neue Version {tag} verfügbar!",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(padx=20, pady=(16, 4))

        ctk.CTkLabel(win, text="Änderungen:", font=ctk.CTkFont(size=11),
                     anchor="w").pack(fill="x", padx=20)
        box = ctk.CTkScrollableFrame(win, fg_color=theme.SURFACE, corner_radius=8, height=180)
        box.pack(fill="x", padx=20, pady=(4, 12))
        ctk.CTkLabel(box, text=changelog, font=ctk.CTkFont(size=10),
                     text_color=theme.TEXT_SOFT, anchor="w", justify="left",
                     wraplength=440).pack(padx=8, pady=8, fill="x")

        progress_var = ctk.StringVar(master=win, value="")
        ctk.CTkLabel(win, textvariable=progress_var, font=ctk.CTkFont(size=10),
                     text_color=theme.MUTED).pack(padx=20)

        bar = ctk.CTkProgressBar(win, width=460)
        bar.set(0)
        bar.pack(padx=20, pady=(4, 8))

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(padx=20, pady=(0, 16), fill="x")

        def on_progress(done, total):          # Download-Thread
            def apply():
                if not win.winfo_exists():
                    return
                if total:
                    bar.set(done / total)
                    progress_var.set(f"{done // 1024} / {total // 1024} KB")
                else:
                    progress_var.set(f"{done // 1024} KB")
            self._ui.submit(apply)

        def on_done(path, error):              # Download-Thread
            def apply():
                if error:
                    if win.winfo_exists():
                        progress_var.set(f"Fehler: {error}")
                        install_btn.configure(state="normal", text="Nochmal versuchen")
                    return
                if win.winfo_exists():
                    progress_var.set("Download abgeschlossen – Installer wird gestartet…")
                if updater.run_installer(path):
                    win.after(800, self._quit)
            self._ui.submit(apply)

        def on_install():
            install_btn.configure(state="disabled", text="Lade herunter…")
            updater.download_installer(release, on_progress, on_done)

        install_btn = ctk.CTkButton(btn_row, text="Jetzt installieren",
                                    width=160, height=36, command=on_install)
        install_btn.pack(side="left")

        ctk.CTkButton(btn_row, text="Zur Download-Seite", width=150, height=36,
                      fg_color="transparent", border_width=1, border_color=theme.BORDER,
                      text_color=theme.TEXT, command=lambda: webbrowser.open(html_url),
                      ).pack(side="left", padx=(8, 0))

        ctk.CTkButton(btn_row, text="Später", width=80, height=36,
                      fg_color="transparent", text_color=theme.TEXT, command=win.destroy,
                      ).pack(side="right")

    def _on_motd(self, motd_id: str, message: str):
        if self._icon and self.cfg.get("notifications", True):
            try:
                self._icon.notify(message, "Scan Watcher")
            except Exception:
                pass
        self.cfg["last_motd_id"] = motd_id
        config.save(self.cfg)

    # ------------------------------------------------------------ Hauptfenster

    def _show_main_window(self):
        import customtkinter as ctk
        if self._existing("main"):
            return
        root = self._new_window("main", "Scan Watcher", "520x500")
        root.resizable(False, False)

        # ── Header ──────────────────────────────────────────────
        header = ctk.CTkFrame(root, fg_color=theme.HEADER_ALT, corner_radius=0)
        header.pack(fill="x")

        img_hdr = _icon_image(40)
        if img_hdr:
            ctk.CTkLabel(header, image=img_hdr, text="").pack(side="left", padx=(16, 8), pady=10)

        title_col = ctk.CTkFrame(header, fg_color="transparent")
        title_col.pack(side="left", pady=10)
        ctk.CTkLabel(title_col, text="Scan Watcher",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(title_col, text=f"v{self.version}  |  Nova Network",
                     font=ctk.CTkFont(size=10), text_color=theme.MUTED).pack(anchor="w")

        dot_frame = ctk.CTkFrame(header, fg_color="transparent")
        dot_frame.pack(side="right", padx=20)
        status_dot = ctk.CTkLabel(dot_frame, text="●", font=ctk.CTkFont(size=20))
        status_dot.pack()
        status_txt = ctk.CTkLabel(dot_frame, text="", font=ctk.CTkFont(size=9),
                                  text_color=theme.MUTED)
        status_txt.pack()

        # ── Tabs ────────────────────────────────────────────────
        tabs = ctk.CTkTabview(
            root, fg_color=theme.BG,
            segmented_button_fg_color=theme.TAB_BAR,
            segmented_button_selected_color=theme.TAB_SELECTED,
            segmented_button_selected_hover_color=theme.TAB_HOVER,
        )
        tabs.pack(fill="both", expand=True)

        # ── Tab: Übersicht ───────────────────────────────────────
        tab_ov = tabs.add("Übersicht")

        count_lbl = ctk.CTkLabel(tab_ov, text="0", font=ctk.CTkFont(size=36, weight="bold"))
        count_lbl.pack(pady=(18, 0))
        ctk.CTkLabel(tab_ov, text="Dateien umbenannt (Session)",
                     font=ctk.CTkFont(size=10), text_color=theme.MUTED).pack()

        ctk.CTkFrame(tab_ov, height=1, fg_color=theme.DIVIDER).pack(fill="x", padx=24, pady=10)

        ctk.CTkLabel(tab_ov, text="Zuletzt verarbeitet",
                     font=ctk.CTkFont(size=11, weight="bold"), anchor="w").pack(fill="x", padx=24)

        recent_box = ctk.CTkFrame(tab_ov, fg_color=theme.SURFACE, corner_radius=6)
        recent_box.pack(fill="x", padx=24, pady=(4, 12))
        recent_labels = []
        for _ in range(5):
            lbl = ctk.CTkLabel(recent_box, text="", anchor="w",
                               font=ctk.CTkFont(size=10, family="Courier New"),
                               text_color=theme.INFO)
            lbl.pack(fill="x", padx=10, pady=2)
            recent_labels.append(lbl)

        ctk.CTkButton(
            tab_ov, text="Verarbeitete Dateien …", height=30,
            fg_color="transparent", border_width=1, border_color=theme.BORDER_SOFT,
            text_color=theme.TEXT, font=ctk.CTkFont(size=10),
            command=self._show_log_window,
        ).pack(pady=(0, 8))

        # ── Tab: Einstellungen ───────────────────────────────────
        tab_set = tabs.add("Einstellungen")
        ctk.CTkLabel(tab_set, text="Konfiguration",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(40, 8))
        ctk.CTkLabel(
            tab_set,
            text="Überwachte Ordner, KI-Modell, Benennungsschema,\nAutostart und weitere Optionen.",
            font=ctk.CTkFont(size=11), text_color=theme.MUTED, justify="center",
        ).pack(pady=(0, 24))
        ctk.CTkButton(tab_set, text="Einstellungen öffnen", width=220, height=42,
                      command=self._open_settings).pack()

        # ── Tab: Unterstützen ────────────────────────────────────
        tab_sup = tabs.add("Unterstützen")
        ctk.CTkLabel(tab_sup, text="☕  Scan Watcher unterstützen",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(40, 8))
        ctk.CTkLabel(
            tab_sup,
            text="Scan Watcher ist kostenlos und Open Source.\nWenn dir das Tool hilft, freue ich mich über einen Kaffee!",
            font=ctk.CTkFont(size=11), text_color=theme.MUTED, justify="center",
        ).pack(pady=(0, 24))
        ctk.CTkButton(tab_sup, text="☕  Ko-fi unterstützen", width=220, height=42,
                      fg_color=theme.KOFI, hover_color=theme.KOFI_HOVER, text_color="white",
                      command=lambda: webbrowser.open(_KOFI_URL)).pack(pady=(0, 10))

        # ── Tab: Über ────────────────────────────────────────────
        tab_about = tabs.add("Über")
        img_big = _icon_image(72)
        if img_big:
            ctk.CTkLabel(tab_about, image=img_big, text="").pack(pady=(24, 6))
        ctk.CTkLabel(tab_about, text=f"Scan Watcher  v{self.version}",
                     font=ctk.CTkFont(size=15, weight="bold")).pack()
        ctk.CTkLabel(tab_about, text="Nova Network  |  Lizenz: MIT  |  2026",
                     font=ctk.CTkFont(size=10), text_color=theme.MUTED).pack(pady=(4, 0))
        ctk.CTkLabel(
            tab_about,
            text="Automatische OCR-Umbenennung für Windows-Scan-Ordner.\nDokumente werden erkannt, sinnvoll benannt und archiviert.",
            font=ctk.CTkFont(size=11), text_color=theme.MUTED, justify="center",
        ).pack(pady=(14, 0))

        # ── Refresh-Schleife ─────────────────────────────────────
        def refresh():
            if not root.winfo_exists():
                return
            running = self._any_running()
            status_dot.configure(text_color=theme.GREEN_DOT if running else theme.RED_DOT)
            status_txt.configure(text="Aktiv" if running else "Gestoppt")
            count_lbl.configure(text=str(get_session_count()))
            recent = get_recent_files()
            for i, lbl in enumerate(recent_labels):
                lbl.configure(text=recent[i] if i < len(recent) else "")
            root.after(2000, refresh)

        refresh()

    # ------------------------------------------------------------ Log-Fenster

    def _recent_menu_items(self):
        recent = get_recent_files()[:5]
        if not recent:
            return [pystray.MenuItem("(noch keine Dateien)", None, enabled=False)]
        return [pystray.MenuItem(name, None, enabled=False) for name in recent]

    def _show_log_window(self):
        import customtkinter as ctk
        if self._existing("log"):
            return
        win = self._new_window("log", "Scan Watcher – Verarbeitete Dateien", "600x400")

        ctk.CTkLabel(win, text="Verarbeitete Dateien (diese Session)",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(padx=20, pady=(16, 8))

        box = ctk.CTkScrollableFrame(win, fg_color=theme.SURFACE, corner_radius=8)
        box.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        files = get_recent_files()
        if files:
            for i, name in enumerate(files, 1):
                ctk.CTkLabel(box, text=f"{i:>3}.  {name}",
                             font=ctk.CTkFont(size=11, family="Courier New"),
                             text_color=theme.ACCENT_TEXT, anchor="w",
                             ).pack(fill="x", padx=12, pady=2)
        else:
            ctk.CTkLabel(box, text="Noch keine Dateien verarbeitet.",
                         text_color=theme.MUTED, anchor="w").pack(padx=12, pady=8)

        ctk.CTkButton(win, text="Schließen", width=100, command=win.destroy).pack(pady=(0, 16))

    # ------------------------------------------------------------ Beenden

    def _quit(self):
        if self._heartbeat_timer:
            self._heartbeat_timer.cancel()
        for w in self._watchers:
            w.stop()
        if self._icon:
            self._icon.stop()   # run() kehrt zurueck, main() beendet den UI-Thread
