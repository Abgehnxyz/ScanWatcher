"""
@file    settings_dialog.py
@project Scan Watcher
@company Nova Network GmbH
@date    Mai 2026
@brief   Einstellungs-Dialog (customtkinter, Dark-Mode) – Ordnerkonfiguration,
         Claude API-Key, Autostart- und Benachrichtigungs-Toggles.
"""

import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import config

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, cfg: dict, on_save=None):
        super().__init__(parent)
        self.cfg = cfg.copy()
        self.on_save = on_save
        self.result = None

        self.title("Scan Watcher – Einstellungen")
        self.resizable(False, False)
        self._build_ui()
        self._center()

    def _build_ui(self):
        self.configure(fg_color="#141420")

        # Header
        header = ctk.CTkFrame(self, fg_color="#0a0a14", corner_radius=0, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="⚙  Scan Watcher",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="white",
        ).pack(side="left", padx=20)

        ctk.CTkLabel(
            header,
            text="Nova Network",
            font=ctk.CTkFont(size=11),
            text_color="#555",
        ).pack(side="right", padx=20)

        # Inhalt
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=24, pady=20)

        self._folder_row(main, "Eingangsordner (Pflicht)", "source_folder")
        self._folder_row(main, "Ausgangsordner (optional)", "target_folder")

        ctk.CTkLabel(
            main,
            text="  ↳  Leer lassen = Dateien werden im Eingangsordner umbenannt",
            font=ctk.CTkFont(size=11),
            text_color="#666",
            anchor="w",
        ).pack(fill="x", pady=(0, 12))

        self._text_row(main, "Claude API-Key (optional)", "anthropic_key", show="*")

        # Trennlinie
        ctk.CTkFrame(main, height=1, fg_color="#2a2a3a").pack(fill="x", pady=16)

        # Toggles
        self._var_autostart = tk.BooleanVar(value=self.cfg.get("autostart", False))
        self._toggle_row(main, "Mit Windows automatisch starten", self._var_autostart)

        self._var_notifications = tk.BooleanVar(value=self.cfg.get("notifications", True))
        self._toggle_row(main, "Windows-Benachrichtigungen anzeigen", self._var_notifications)

        # Footer mit Buttons
        footer = ctk.CTkFrame(self, fg_color="#0a0a14", corner_radius=0, height=60)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        ctk.CTkButton(
            footer,
            text="Speichern",
            width=120,
            height=36,
            command=self._save,
        ).pack(side="right", padx=(8, 20), pady=12)

        ctk.CTkButton(
            footer,
            text="Abbrechen",
            width=100,
            height=36,
            fg_color="transparent",
            border_width=1,
            border_color="#444",
            hover_color="#2a2a3a",
            command=self.destroy,
        ).pack(side="right", pady=12)

    def _folder_row(self, parent: ctk.CTkFrame, label: str, key: str):
        ctk.CTkLabel(
            parent, text=label, anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(fill="x", pady=(0, 4))

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 10))

        var = tk.StringVar(value=self.cfg.get(key, ""))
        ctk.CTkEntry(
            row, textvariable=var, height=36,
            placeholder_text="Ordner wählen...",
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            row, text="…", width=42, height=36,
            command=lambda v=var: v.set(
                filedialog.askdirectory(initialdir=v.get() or "/") or v.get()
            ),
        ).pack(side="right")

        setattr(self, f"_var_{key}", var)

    def _text_row(self, parent: ctk.CTkFrame, label: str, key: str, show: str | None = None):
        ctk.CTkLabel(
            parent, text=label, anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(fill="x", pady=(0, 4))

        var = tk.StringVar(value=self.cfg.get(key, ""))
        kw = {"show": show} if show else {}
        ctk.CTkEntry(parent, textvariable=var, height=36, **kw).pack(fill="x", pady=(0, 10))
        setattr(self, f"_var_{key}", var)

    def _toggle_row(self, parent: ctk.CTkFrame, label: str, var: tk.BooleanVar):
        row = ctk.CTkFrame(parent, fg_color="#1e1e2e", corner_radius=8)
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text=label, anchor="w").pack(side="left", padx=16, pady=12)
        ctk.CTkSwitch(
            row, text="", variable=var, onvalue=True, offvalue=False, width=48,
        ).pack(side="right", padx=16)

    def _save(self):
        for key in ("source_folder", "target_folder", "anthropic_key"):
            var = getattr(self, f"_var_{key}", None)
            if var:
                self.cfg[key] = var.get().strip()
        self.cfg["autostart"] = self._var_autostart.get()
        self.cfg["notifications"] = self._var_notifications.get()

        if not self.cfg["source_folder"]:
            messagebox.showerror("Fehler", "Bitte den Eingangsordner angeben.")
            return

        config.save(self.cfg)
        self.result = self.cfg
        if self.on_save:
            self.on_save(self.cfg)
        self.destroy()

    def _center(self):
        w, h = 520, 540
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
