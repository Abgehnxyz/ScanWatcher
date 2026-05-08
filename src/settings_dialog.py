"""
@file    settings_dialog.py
@project Scan Watcher
@company Nova Network
@date    Mai 2026
@brief   Einstellungs-Dialog (customtkinter, Dark-Mode) – Ordnerkonfiguration,
         KI-Modell-Auswahl, Benennungsschema, Autostart- und Benachrichtigungs-Toggles.
"""

import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import config

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

_MODEL_OPTIONS = [
    ("rules",   "Keines – Regelwerk (offline)"),
    ("claude",  "Claude Haiku (Anthropic)"),
    ("openai",  "GPT-4o-mini (OpenAI)"),
    ("gemini",  "Gemini Flash (Google)"),
    ("mistral", "Mistral Small (EU-Server)"),
    ("groq",    "Llama 3.1 via Groq"),
    ("ollama",  "Ollama (lokal, kein Internet)"),
]
_MODEL_ID      = {display: key for key, display in _MODEL_OPTIONS}
_MODEL_DISPLAY = {key: display for key, display in _MODEL_OPTIONS}

_MODEL_DETAIL = {
    "rules": {
        "has_key": False,
        "info":  "Umbenennung per Regelwerk – erkennt Datum, Absender und Betreff aus dem OCR-Text.",
        "info2": "Kein Internet, keine Kosten.",
        "color": "#666",
    },
    "claude": {
        "has_key": True,
        "hint":    "API-Key: console.anthropic.com  |  ~$0.001/Dok. (claude-3-5-haiku)",
        "warning": "OCR-Text wird an US-Server (Anthropic) uebermittelt.",
        "color":   "#e07020",
    },
    "openai": {
        "has_key": True,
        "hint":    "API-Key: platform.openai.com  |  ~$0.0002/Dok. (gpt-4o-mini)",
        "warning": "OCR-Text wird an US-Server (OpenAI) uebermittelt.",
        "color":   "#e07020",
    },
    "gemini": {
        "has_key": True,
        "hint":    "API-Key: aistudio.google.com  |  Kostenloser Tier: 1.500 Anfragen/Tag",
        "warning": "OCR-Text wird an US-Server (Google) uebermittelt.",
        "color":   "#e07020",
    },
    "mistral": {
        "has_key": True,
        "hint":    "API-Key: console.mistral.ai  |  ~$0.001/Dok. – EU-Server (DSGVO-freundlich)",
        "warning": "OCR-Text wird an EU-Server (Mistral AI, Frankreich) uebermittelt.",
        "color":   "#4488cc",
    },
    "groq": {
        "has_key": True,
        "hint":    "API-Key: console.groq.com  |  Kostenloser Tier, sehr schnell",
        "warning": "OCR-Text wird an US-Server (Groq) uebermittelt.",
        "color":   "#e07020",
    },
    "ollama": {
        "has_key": False,
        "info":  "Laeuft lokal auf Port 11434 – kein Internet, keine Kosten.",
        "info2": "Installieren: ollama.com  |  Modell laden: ollama pull llama3.2",
        "color": "#4488cc",
    },
}


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

        main = ctk.CTkScrollableFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=24, pady=20)

        self._folder_row(main, "Eingangsordner (Pflicht)", "source_folder")
        self._folder_row(main, "Ausgangsordner (optional)", "target_folder")

        ctk.CTkLabel(
            main,
            text="  Leer lassen = Dateien werden im Eingangsordner umbenannt",
            font=ctk.CTkFont(size=11),
            text_color="#666",
            anchor="w",
        ).pack(fill="x", pady=(0, 12))

        ctk.CTkFrame(main, height=1, fg_color="#2a2a3a").pack(fill="x", pady=(0, 16))
        self._naming_section(main)
        ctk.CTkFrame(main, height=1, fg_color="#2a2a3a").pack(fill="x", pady=16)
        self._model_section(main)
        ctk.CTkFrame(main, height=1, fg_color="#2a2a3a").pack(fill="x", pady=16)
        self._senders_section(main)
        ctk.CTkFrame(main, height=1, fg_color="#2a2a3a").pack(fill="x", pady=16)
        self._doc_types_section(main)
        ctk.CTkFrame(main, height=1, fg_color="#2a2a3a").pack(fill="x", pady=16)

        # Toggles
        self._var_autostart = tk.BooleanVar(value=self.cfg.get("autostart", False))
        self._toggle_row(main, "Mit Windows automatisch starten", self._var_autostart)

        self._var_notifications = tk.BooleanVar(value=self.cfg.get("notifications", True))
        self._toggle_row(main, "Windows-Benachrichtigungen anzeigen", self._var_notifications)

        self._option_row(main, "Log-Level (Protokollierung)", "log_level", ["INFO", "DEBUG", "WARNING"])

        ctk.CTkFrame(main, height=1, fg_color="#2a2a3a").pack(fill="x", pady=16)

        # Telemetrie
        ctk.CTkLabel(
            main,
            text="Nutzungsstatistiken",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self._var_telemetry = tk.BooleanVar(value=self.cfg.get("telemetry_enabled", False))
        row_tel = ctk.CTkFrame(main, fg_color="#1e1e2e", corner_radius=8)
        row_tel.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(row_tel, text="Anonyme Nutzungsstatistiken senden", anchor="w").pack(
            side="left", padx=16, pady=12
        )
        ctk.CTkSwitch(
            row_tel, text="", variable=self._var_telemetry, onvalue=True, offvalue=False, width=48
        ).pack(side="right", padx=16)

        ctk.CTkLabel(
            main,
            text="  Kein Personenbezug. Nur: App-Version, Modell, Erfolg/Fehler. Daten gehen an ops.abgehn.xyz.",
            font=ctk.CTkFont(size=10),
            text_color="#4488cc",
            anchor="w",
            wraplength=460,
        ).pack(fill="x", pady=(0, 12))

        # Footer
        footer = ctk.CTkFrame(self, fg_color="#0a0a14", corner_radius=0, height=60)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        ctk.CTkButton(
            footer, text="Speichern", width=120, height=36, command=self._save,
        ).pack(side="right", padx=(8, 20), pady=12)

        ctk.CTkButton(
            footer, text="Abbrechen", width=100, height=36,
            fg_color="transparent", border_width=1, border_color="#444",
            hover_color="#2a2a3a", command=self.destroy,
        ).pack(side="right", pady=12)

    # ------------------------------------------------------------------ Modell

    def _model_section(self, parent: ctk.CTkFrame):
        self._model_keys = {
            m: config.get_model_key(m)
            for m in ("claude", "openai", "gemini", "mistral", "groq")
        }
        self._current_model = self.cfg.get("active_model", "rules")

        ctk.CTkLabel(
            parent,
            text="KI-Modell fuer Umbenennung",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 6))

        display_values = [d for _, d in _MODEL_OPTIONS]
        self._om_active_model = ctk.CTkOptionMenu(
            parent,
            values=display_values,
            height=36,
            command=self._on_model_change,
        )
        self._om_active_model.set(_MODEL_DISPLAY.get(self._current_model, display_values[0]))
        self._om_active_model.pack(fill="x", pady=(0, 8))

        self._model_detail_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._model_detail_frame.pack(fill="x")

        self._rebuild_model_detail(self._current_model)

    def _on_model_change(self, display_value: str):
        self._capture_current_model_key()
        self._current_model = _MODEL_ID.get(display_value, "rules")
        self._rebuild_model_detail(self._current_model)

    def _capture_current_model_key(self):
        m = getattr(self, "_current_model", "rules")
        if m in ("rules", "ollama"):
            return
        var = getattr(self, f"_var_{m}_key", None)
        if var:
            self._model_keys[m] = var.get().strip()

    def _rebuild_model_detail(self, model_key: str):
        for w in self._model_detail_frame.winfo_children():
            w.destroy()
        p = self._model_detail_frame
        d = _MODEL_DETAIL.get(model_key, _MODEL_DETAIL["rules"])

        if model_key == "ollama":
            self._text_row(p, "Ollama-Modell (z. B. llama3.2, mistral, gemma3)", "ollama_model")
            ctk.CTkLabel(
                p,
                text=f"  {d['info']}\n  {d['info2']}",
                font=ctk.CTkFont(size=10),
                text_color=d["color"],
                anchor="w",
                wraplength=460,
            ).pack(fill="x", pady=(0, 4))

        elif d.get("has_key"):
            var = tk.StringVar(value=self._model_keys.get(model_key, ""))
            setattr(self, f"_var_{model_key}_key", var)
            ctk.CTkEntry(
                p, textvariable=var, show="*", height=36,
                placeholder_text="API-Key eingeben...",
            ).pack(fill="x", pady=(0, 4))
            ctk.CTkLabel(
                p,
                text=f"  {d['hint']}",
                font=ctk.CTkFont(size=10),
                text_color="#4488cc",
                anchor="w",
                wraplength=460,
            ).pack(fill="x")
            ctk.CTkLabel(
                p,
                text=f"  {d['warning']}",
                font=ctk.CTkFont(size=10),
                text_color=d["color"],
                anchor="w",
                wraplength=460,
            ).pack(fill="x", pady=(0, 4))

        else:  # rules
            ctk.CTkLabel(
                p,
                text=f"  {d['info']}\n  {d['info2']}",
                font=ctk.CTkFont(size=10),
                text_color=d["color"],
                anchor="w",
                wraplength=460,
            ).pack(fill="x", pady=(0, 4))

    # ---------------------------------------------------- Benennungsschema

    def _naming_section(self, parent: ctk.CTkFrame):
        ctk.CTkLabel(
            parent,
            text="Benennungsschema",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self._var_name_template = tk.StringVar(
            value=self.cfg.get("name_template", "{DATUM}_{ABSENDER}_{BETREFF}")
        )
        ctk.CTkEntry(
            parent,
            textvariable=self._var_name_template,
            height=36,
            placeholder_text="{DATUM}_{ABSENDER}_{BETREFF}",
        ).pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            parent,
            text="  Tokens: {DATUM}  {JAHR}  {MONAT}  {TAG}  {ABSENDER}  {BETREFF}  {ORIGINAL}",
            font=ctk.CTkFont(size=10),
            text_color="#666",
            anchor="w",
        ).pack(fill="x", pady=(0, 10))

        row_fmt = ctk.CTkFrame(parent, fg_color="transparent")
        row_fmt.pack(fill="x", pady=(0, 4))

        fmt_frame = ctk.CTkFrame(row_fmt, fg_color="transparent")
        fmt_frame.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkLabel(fmt_frame, text="Datumsformat", font=ctk.CTkFont(size=11), anchor="w").pack(fill="x")
        self._om_date_format = ctk.CTkOptionMenu(
            fmt_frame,
            values=["YYYY-MM-DD", "DD.MM.YYYY", "YYYYMMDD"],
            height=32,
            command=lambda _: self._update_preview(),
        )
        self._om_date_format.set(self.cfg.get("date_format", "YYYY-MM-DD"))
        self._om_date_format.pack(fill="x")

        sep_frame = ctk.CTkFrame(row_fmt, fg_color="transparent")
        sep_frame.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(sep_frame, text="Leerzeichen ersetzen durch", font=ctk.CTkFont(size=11), anchor="w").pack(fill="x")
        self._om_space_replacement = ctk.CTkOptionMenu(
            sep_frame,
            values=["- (Bindestrich)", "_ (Unterstrich)"],
            height=32,
            command=lambda _: self._update_preview(),
        )
        current_sr = self.cfg.get("space_replacement", "-")
        self._om_space_replacement.set("_ (Unterstrich)" if current_sr == "_" else "- (Bindestrich)")
        self._om_space_replacement.pack(fill="x")

        preview_frame = ctk.CTkFrame(parent, fg_color="#1e1e2e", corner_radius=8)
        preview_frame.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(
            preview_frame, text="Vorschau:",
            font=ctk.CTkFont(size=10), text_color="#888", anchor="w",
        ).pack(side="left", padx=(12, 6), pady=10)
        self._preview_label = ctk.CTkLabel(
            preview_frame, text="",
            font=ctk.CTkFont(size=11, family="Courier New"),
            text_color="#88ccff", anchor="w",
        )
        self._preview_label.pack(side="left", fill="x", expand=True, padx=(0, 12), pady=10)

        self._var_name_template.trace_add("write", lambda *_: self._update_preview())
        self._update_preview()

    def _update_preview(self):
        from . import renamer
        template = self._var_name_template.get() or "{DATUM}_{ABSENDER}_{BETREFF}"
        date_format = self._om_date_format.get()
        sr = self._om_space_replacement.get()
        space_replacement = "_" if sr.startswith("_") else "-"
        try:
            example = renamer.apply_template(
                template,
                datum_raw="2026-05-08",
                absender="Nova Network",
                betreff="Lizenz Rechnung",
                original_stem="20260508",
                date_format=date_format,
                space_replacement=space_replacement,
            )
            self._preview_label.configure(text=example + ".pdf")
        except Exception:
            self._preview_label.configure(text="—")

    # ------------------------------------------------------- Absender-Whitelist

    def _senders_section(self, parent: ctk.CTkFrame):
        ctk.CTkLabel(
            parent,
            text="Absender-Whitelist",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            parent,
            text="  Suchbegriff im OCR-Text → Anzeigename  (Vorrang vor eingebautem Regelwerk)",
            font=ctk.CTkFont(size=10),
            text_color="#666",
            anchor="w",
        ).pack(fill="x", pady=(0, 8))

        self._sender_rows_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._sender_rows_frame.pack(fill="x")

        self._sender_rows: list[tuple] = []

        for key, val in self.cfg.get("custom_senders", {}).items():
            self._add_sender_row(key, val)

        ctk.CTkButton(
            parent,
            text="+ Eintrag hinzufügen",
            height=32,
            fg_color="transparent",
            border_width=1,
            border_color="#444",
            hover_color="#2a2a3a",
            command=lambda: self._add_sender_row("", ""),
        ).pack(anchor="w", pady=(6, 0))

    def _add_sender_row(self, key: str = "", value: str = ""):
        row = ctk.CTkFrame(self._sender_rows_frame, fg_color="#1e1e2e", corner_radius=8)
        row.pack(fill="x", pady=(0, 4))

        kv = tk.StringVar(value=key)
        vv = tk.StringVar(value=value)

        ctk.CTkEntry(
            row, textvariable=kv, height=32, placeholder_text="Suchbegriff…"
        ).pack(side="left", fill="x", expand=True, padx=(8, 4), pady=6)

        ctk.CTkLabel(row, text="→", text_color="#888", width=20).pack(side="left", padx=2)

        ctk.CTkEntry(
            row, textvariable=vv, height=32, placeholder_text="Anzeigename…"
        ).pack(side="left", fill="x", expand=True, padx=(4, 4), pady=6)

        entry = (kv, vv, row)
        self._sender_rows.append(entry)

        ctk.CTkButton(
            row, text="✕", width=32, height=32,
            fg_color="transparent", hover_color="#3a2a2a", text_color="#cc4444",
            command=lambda t=entry: self._remove_sender_row(t),
        ).pack(side="right", padx=(0, 6), pady=6)

    def _remove_sender_row(self, entry_tuple: tuple):
        if entry_tuple in self._sender_rows:
            self._sender_rows.remove(entry_tuple)
        entry_tuple[2].destroy()

    # ----------------------------------------------------- Dokumenttypen

    def _doc_types_section(self, parent: ctk.CTkFrame):
        ctk.CTkLabel(
            parent,
            text="Dokumenttypen",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            parent,
            text="  Suchbegriff im OCR-Text → Anzeigename  (Vorrang vor eingebautem Regelwerk)",
            font=ctk.CTkFont(size=10),
            text_color="#666",
            anchor="w",
        ).pack(fill="x", pady=(0, 8))

        self._doc_type_rows_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._doc_type_rows_frame.pack(fill="x")

        self._doc_type_rows: list[tuple] = []

        for key, val in self.cfg.get("custom_doc_types", {}).items():
            self._add_doc_type_row(key, val)

        ctk.CTkButton(
            parent,
            text="+ Eintrag hinzufügen",
            height=32,
            fg_color="transparent",
            border_width=1,
            border_color="#444",
            hover_color="#2a2a3a",
            command=lambda: self._add_doc_type_row("", ""),
        ).pack(anchor="w", pady=(6, 0))

    def _add_doc_type_row(self, key: str = "", value: str = ""):
        row = ctk.CTkFrame(self._doc_type_rows_frame, fg_color="#1e1e2e", corner_radius=8)
        row.pack(fill="x", pady=(0, 4))

        kv = tk.StringVar(value=key)
        vv = tk.StringVar(value=value)

        ctk.CTkEntry(
            row, textvariable=kv, height=32, placeholder_text="Suchbegriff…"
        ).pack(side="left", fill="x", expand=True, padx=(8, 4), pady=6)

        ctk.CTkLabel(row, text="→", text_color="#888", width=20).pack(side="left", padx=2)

        ctk.CTkEntry(
            row, textvariable=vv, height=32, placeholder_text="Anzeigename…"
        ).pack(side="left", fill="x", expand=True, padx=(4, 4), pady=6)

        entry = (kv, vv, row)
        self._doc_type_rows.append(entry)

        ctk.CTkButton(
            row, text="✕", width=32, height=32,
            fg_color="transparent", hover_color="#3a2a2a", text_color="#cc4444",
            command=lambda t=entry: self._remove_doc_type_row(t),
        ).pack(side="right", padx=(0, 6), pady=6)

    def _remove_doc_type_row(self, entry_tuple: tuple):
        if entry_tuple in self._doc_type_rows:
            self._doc_type_rows.remove(entry_tuple)
        entry_tuple[2].destroy()

    # --------------------------------------------------------- Hilfs-Methoden

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
            placeholder_text="Ordner waehlen...",
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            row, text="...", width=42, height=36,
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

    def _option_row(self, parent: ctk.CTkFrame, label: str, key: str, options: list):
        ctk.CTkLabel(
            parent, text=label, anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(fill="x", pady=(8, 4))
        current = self.cfg.get(key, options[0])
        om = ctk.CTkOptionMenu(parent, values=options, height=36)
        om.set(current)
        om.pack(fill="x", pady=(0, 4))
        setattr(self, f"_om_{key}", om)

    def _save(self):
        for key in ("source_folder", "target_folder"):
            var = getattr(self, f"_var_{key}", None)
            if var:
                self.cfg[key] = var.get().strip()

        self.cfg["autostart"]         = self._var_autostart.get()
        self.cfg["notifications"]     = self._var_notifications.get()
        self.cfg["log_level"]         = self._om_log_level.get()
        self.cfg["telemetry_enabled"] = self._var_telemetry.get()
        self.cfg["name_template"]     = self._var_name_template.get().strip() or "{DATUM}_{ABSENDER}_{BETREFF}"
        self.cfg["date_format"]       = self._om_date_format.get()
        sr = self._om_space_replacement.get()
        self.cfg["space_replacement"] = "_" if sr.startswith("_") else "-"

        # Aktives Modell + API-Keys
        self._capture_current_model_key()
        self.cfg["active_model"] = _MODEL_ID.get(self._om_active_model.get(), "rules")
        for m, key in self._model_keys.items():
            config.set_model_key(m, key)
        ollama_var = getattr(self, "_var_ollama_model", None)
        self.cfg["ollama_model"] = ollama_var.get().strip() if ollama_var else self.cfg.get("ollama_model", "llama3.2")

        custom_senders = {}
        for kv, vv, _ in getattr(self, "_sender_rows", []):
            k = kv.get().strip()
            v = vv.get().strip()
            if k:
                custom_senders[k] = v
        self.cfg["custom_senders"] = custom_senders

        custom_doc_types = {}
        for kv, vv, _ in getattr(self, "_doc_type_rows", []):
            k = kv.get().strip()
            v = vv.get().strip()
            if k:
                custom_doc_types[k] = v
        self.cfg["custom_doc_types"] = custom_doc_types

        if not self.cfg["source_folder"]:
            messagebox.showerror("Fehler", "Bitte den Eingangsordner angeben.")
            return

        config.save(self.cfg)
        self.result = self.cfg
        if self.on_save:
            self.on_save(self.cfg)
        self.destroy()

    def _center(self):
        w, h = 520, 800
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        h = min(h, sh - 100)
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
