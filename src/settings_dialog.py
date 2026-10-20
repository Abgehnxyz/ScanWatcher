"""
@file    settings_dialog.py
@project Scan Watcher
@company Nova Network
@date    Mai 2026
@brief   Einstellungs-Dialog (customtkinter, Dark-Mode) – Ordnerkonfiguration,
         KI-Modell-Auswahl, Benennungsschema, Autostart- und Benachrichtigungs-Toggles.
"""

import re
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import config, renamer, theme

_MODEL_OPTIONS = [
    ("rules",   "Keines – Regelwerk (offline)"),
    ("ollama",  "Ollama (lokal oder eigener Server)"),
    ("custom",  "OpenAI-kompatibel (LM Studio, vLLM, OpenRouter …)"),
    ("claude",  "Claude Haiku (Anthropic)"),
    ("openai",  "OpenAI"),
    ("gemini",  "Gemini Flash (Google)"),
    ("mistral", "Mistral Small (EU-Server)"),
    ("groq",    "Groq (sehr schnell)"),
]
_MODEL_ID      = {display: key for key, display in _MODEL_OPTIONS}
_MODEL_DISPLAY = {key: display for key, display in _MODEL_OPTIONS}

def _mask_key(key: str) -> str:
    """Zeigt erste 6 + ••••••• + letzte 4 Zeichen eines API-Keys."""
    if not key:
        return ""
    if len(key) <= 12:
        return key[:2] + "•" * max(1, len(key) - 2)
    return key[:6] + "•" * 8 + key[-4:]


_MODEL_DETAIL = {
    "rules": {
        "info":  "Umbenennung per Regelwerk – erkennt Datum, Absender und Betreff aus dem OCR-Text.",
        "info2": "Kein Internet, keine Kosten.",
        "color": theme.SUBTLE,
    },
    "ollama": {
        "hint":    "Installieren: ollama.com  |  Modell laden: ollama pull llama3.1",
        "warning": "Lokal oder im eigenen Netz – der OCR-Text bleibt bei dir.",
        "color":   theme.OK,
        "key_label": "API-Key (optional – nur für geschützte Server)",
    },
    "custom": {
        "hint":    "Basis-URL endet meist auf /v1 – z. B. http://localhost:1234/v1 (LM Studio), "
                   "http://server:8000/v1 (vLLM), https://openrouter.ai/api/v1",
        "warning": "OCR-Text wird an den eingetragenen Server übermittelt.",
        "color":   theme.WARN,
        "key_label": "API-Key (optional – lokale Server brauchen meist keinen)",
    },
    "claude": {
        "hint":    "API-Key: console.anthropic.com  |  unter $0.001/Dok.",
        "warning": "OCR-Text wird an US-Server (Anthropic) uebermittelt.",
        "color":   theme.WARN,
    },
    "openai": {
        "hint":    "API-Key: platform.openai.com  |  Preise: openai.com/api/pricing",
        "warning": "OCR-Text wird an US-Server (OpenAI) uebermittelt.",
        "color":   theme.WARN,
    },
    "gemini": {
        "hint":    "API-Key: aistudio.google.com  |  Kostenloses Kontingent verfügbar",
        "warning": "OCR-Text wird an US-Server (Google) uebermittelt.",
        "color":   theme.WARN,
    },
    "mistral": {
        "hint":    "API-Key: console.mistral.ai  |  ~$0.001/Dok. – EU-Server (DSGVO-freundlich)",
        "warning": "OCR-Text wird an EU-Server (Mistral AI, Frankreich) uebermittelt.",
        "color":   theme.INFO,
    },
    "groq": {
        "hint":    "API-Key: console.groq.com  |  Kostenloses Kontingent, sehr schnell",
        "warning": "OCR-Text wird an US-Server (Groq) uebermittelt.",
        "color":   theme.WARN,
    },
}


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, cfg: dict, on_save=None, version: str = ""):
        super().__init__(parent)
        self.cfg = cfg.copy()
        self.on_save = on_save
        self.version = version
        self.result = None
        # Eigene Modell-IDs pro Anbieter (leer = Standard aus renamer)
        self._model_id_vars = {
            m: tk.StringVar(master=self, value=self.cfg.get("model_ids", {}).get(m, ""))
            for m in config.KEY_MODELS
        }
        self._var_ollama_url = tk.StringVar(
            master=self, value=self.cfg.get("ollama_url") or renamer.DEFAULT_OLLAMA_URL)
        self._var_ollama_model = tk.StringVar(master=self, value=self.cfg.get("ollama_model", ""))
        self._var_custom_base_url = tk.StringVar(master=self, value=self.cfg.get("custom_base_url", ""))

        theme.prepare_window(self, "Scan Watcher – Einstellungen")
        self.resizable(False, False)
        self._build_ui()
        self._center()

    def _build_ui(self):

        # Header
        header = ctk.CTkFrame(self, fg_color=theme.HEADER, corner_radius=0, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="⚙  Scan Watcher",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme.TEXT,
        ).pack(side="left", padx=(20, 6))

        if self.version:
            ctk.CTkLabel(
                header,
                text=f"v{self.version}",
                font=ctk.CTkFont(size=11),
                text_color=theme.MUTED,
            ).pack(side="left", pady=(6, 0))

        ctk.CTkButton(
            header,
            text="☕ Unterstützen",
            font=ctk.CTkFont(size=11),
            width=130, height=32,
            fg_color=theme.KOFI, hover_color=theme.KOFI_HOVER, text_color="white",
            command=lambda: __import__("webbrowser").open("https://ko-fi.com/novanetwork"),
        ).pack(side="right", padx=16)

        main = self._make_scroll_area()

        self._profiles_section(main)

        ctk.CTkFrame(main, height=1, fg_color=theme.DIVIDER).pack(fill="x", pady=(0, 16))
        self._naming_section(main)
        ctk.CTkFrame(main, height=1, fg_color=theme.DIVIDER).pack(fill="x", pady=16)
        self._model_section(main)
        ctk.CTkFrame(main, height=1, fg_color=theme.DIVIDER).pack(fill="x", pady=16)
        self._senders_section(main)
        ctk.CTkFrame(main, height=1, fg_color=theme.DIVIDER).pack(fill="x", pady=16)
        self._doc_types_section(main)
        ctk.CTkFrame(main, height=1, fg_color=theme.DIVIDER).pack(fill="x", pady=16)
        self._watcher_section(main)
        ctk.CTkFrame(main, height=1, fg_color=theme.DIVIDER).pack(fill="x", pady=16)

        # Toggles
        self._var_autostart = tk.BooleanVar(value=self.cfg.get("autostart", False))
        self._toggle_row(main, "Mit Windows automatisch starten", self._var_autostart)

        self._var_notifications = tk.BooleanVar(value=self.cfg.get("notifications", True))
        self._toggle_row(main, "Windows-Benachrichtigungen anzeigen", self._var_notifications)

        self._option_row(main, "Log-Level (Protokollierung)", "log_level", ["INFO", "DEBUG", "WARNING"])

        # Darstellung
        ctk.CTkLabel(
            main, text="Darstellung", anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(fill="x", pady=(8, 4))
        self._om_appearance = ctk.CTkOptionMenu(
            main, values=list(theme.APPEARANCE_MODES.values()), height=36,
        )
        self._om_appearance.set(
            theme.APPEARANCE_MODES.get(self.cfg.get("appearance_mode", "dark"), "Dunkel")
        )
        self._om_appearance.pack(fill="x", pady=(0, 4))

        ctk.CTkFrame(main, height=1, fg_color=theme.DIVIDER).pack(fill="x", pady=16)

        # Update-Einstellungen
        ctk.CTkLabel(
            main,
            text="Updates",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self._var_update_check = tk.BooleanVar(value=self.cfg.get("update_check_enabled", True))
        self._toggle_row(main, "Automatisch auf Updates prüfen", self._var_update_check)

        row_ch = ctk.CTkFrame(main, fg_color="transparent")
        row_ch.pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(row_ch, text="Update-Kanal", font=ctk.CTkFont(size=11),
                     anchor="w").pack(side="left")
        self._om_update_channel = ctk.CTkOptionMenu(
            row_ch, values=["Stabil (stable)", "Beta (pre-release)"], width=180, height=32,
        )
        self._om_update_channel.set(
            "Beta (pre-release)" if self.cfg.get("update_channel") == "beta"
            else "Stabil (stable)"
        )
        self._om_update_channel.pack(side="right")

        row_now = ctk.CTkFrame(main, fg_color="transparent")
        row_now.pack(fill="x", pady=(8, 0))
        self._btn_check_now = ctk.CTkButton(
            row_now,
            text="Jetzt auf Updates prüfen",
            width=220,
            height=32,
            command=self._check_update_now,
        )
        self._btn_check_now.pack(side="left")
        self._lbl_check_result = ctk.CTkLabel(
            row_now, text="", font=ctk.CTkFont(size=11),
            anchor="w", text_color=theme.MUTED,
        )
        self._lbl_check_result.pack(side="left", padx=(12, 0))

        ctk.CTkFrame(main, height=1, fg_color=theme.DIVIDER).pack(fill="x", pady=16)

        # Telemetrie
        ctk.CTkLabel(
            main,
            text="Nutzungsstatistiken",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self._var_telemetry = tk.BooleanVar(value=self.cfg.get("telemetry_enabled", False))
        row_tel = ctk.CTkFrame(main, fg_color=theme.SURFACE, corner_radius=8)
        row_tel.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(row_tel, text="Anonyme Nutzungsstatistiken senden", anchor="w").pack(
            side="left", padx=16, pady=12
        )
        ctk.CTkSwitch(
            row_tel, text="", variable=self._var_telemetry, onvalue=True, offvalue=False, width=48
        ).pack(side="right", padx=16)

        ctk.CTkLabel(
            main,
            text="  Kein Personenbezug. Nur: App-Version, genutztes Modell, Erfolg/Fehler.\n"
                 "  Mit Zustimmung werden auch Hinweise von unserem Server abgerufen.",
            font=ctk.CTkFont(size=10),
            text_color=theme.INFO,
            anchor="w",
            wraplength=460,
        ).pack(fill="x", pady=(0, 12))

        # Footer
        footer = ctk.CTkFrame(self, fg_color=theme.HEADER, corner_radius=0, height=60)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        ctk.CTkButton(
            footer, text="Speichern", width=120, height=36, command=self._save,
        ).pack(side="right", padx=(8, 20), pady=12)

        ctk.CTkButton(
            footer, text="Abbrechen", width=100, height=36,
            fg_color="transparent", border_width=1, border_color=theme.BORDER,
            text_color=theme.TEXT,
            hover_color=theme.DIVIDER, command=self.destroy,
        ).pack(side="right", pady=12)

        ctk.CTkButton(
            footer, text="Importieren", width=100, height=36,
            fg_color="transparent", border_width=1, border_color=theme.BORDER,
            text_color=theme.TEXT,
            hover_color=theme.DIVIDER, command=self._import_settings,
        ).pack(side="left", padx=(20, 4), pady=12)

        ctk.CTkButton(
            footer, text="Exportieren", width=100, height=36,
            fg_color="transparent", border_width=1, border_color=theme.BORDER,
            text_color=theme.TEXT,
            hover_color=theme.DIVIDER, command=self._export_settings,
        ).pack(side="left", padx=(0, 4), pady=12)

    # --------------------------------------------------------- Scroll-Bereich

    def _make_scroll_area(self) -> ctk.CTkFrame:
        """Flicker-freier Scrollbereich: tk.Canvas + CTkScrollbar statt CTkScrollableFrame."""
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, bg=theme.resolve(theme.BG), highlightthickness=0, bd=0)
        sb = ctk.CTkScrollbar(container, command=canvas.yview)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=sb.set)

        inner = ctk.CTkFrame(canvas, fg_color="transparent")
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(win_id, width=e.width))

        def _scroll(e):
            # Nur Ereignisse aus diesem Dialog – andere Fenster teilen sich den Tk-Thread
            if not str(getattr(e, "widget", "")).startswith(str(self)):
                return
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        # bind_all wirkt app-weit: eigene Bindung anhaengen (add="+") und beim
        # Schliessen gezielt nur diese wieder entfernen. Toplevel-Bindungen auf
        # <Destroy> feuern auch fuer jedes Kind-Widget – daher e.widget pruefen.
        funcid = self.bind_all("<MouseWheel>", _scroll, add="+")

        def _unbind(e):
            if e.widget is not self:
                return
            script = self.tk.call("bind", "all", "<MouseWheel>")
            kept = "\n".join(l for l in str(script).split("\n") if funcid not in l)
            self.tk.call("bind", "all", "<MouseWheel>", kept)
            self.deletecommand(funcid)

        self.bind("<Destroy>", _unbind, add="+")

        # Padding-Wrapper – entspricht dem früheren padx=24, pady=20
        padded = ctk.CTkFrame(inner, fg_color="transparent")
        padded.pack(fill="x", padx=24, pady=20)
        return padded

    # --------------------------------------------------------- Ordner-Profile

    def _profiles_section(self, parent: ctk.CTkFrame):
        ctk.CTkLabel(
            parent,
            text="Ordner-Profile",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            parent,
            text="  Jeder Eintrag überwacht einen eigenen Eingangsordner gleichzeitig.",
            font=ctk.CTkFont(size=10),
            text_color=theme.SUBTLE,
            anchor="w",
        ).pack(fill="x", pady=(0, 8))

        self._profile_rows_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._profile_rows_frame.pack(fill="x")

        self._profile_rows: list[list] = []

        for p in self.cfg.get("folder_profiles", []):
            self._add_profile_row(p.get("name", ""), p.get("source", ""), p.get("target", ""))

        if not self._profile_rows:
            self._add_profile_row("Standard", "", "")

        ctk.CTkButton(
            parent,
            text="+ Profil hinzufügen",
            height=32,
            fg_color="transparent",
            text_color=theme.TEXT,
            border_width=1,
            border_color=theme.BORDER,
            hover_color=theme.DIVIDER,
            command=lambda: self._add_profile_row("", "", ""),
        ).pack(anchor="w", pady=(6, 0))

    def _add_profile_row(self, name: str = "", source: str = "", target: str = ""):
        outer = ctk.CTkFrame(self._profile_rows_frame, fg_color=theme.SURFACE, corner_radius=8)
        outer.pack(fill="x", pady=(0, 6))

        header = ctk.CTkFrame(outer, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(6, 2))

        name_var = tk.StringVar(value=name)
        ctk.CTkEntry(
            header, textvariable=name_var, height=28,
            placeholder_text="Profil-Name…",
        ).pack(side="left", fill="x", expand=True)

        entry: list = [name_var, None, None, outer]
        self._profile_rows.append(entry)

        ctk.CTkButton(
            header, text="✕", width=28, height=28,
            fg_color="transparent", hover_color=theme.DANGER_HOVER, text_color=theme.DANGER,
            command=lambda e=entry: self._remove_profile_row(e),
        ).pack(side="right", padx=(8, 0))

        def _folder_entry(row_frame, label_text: str, initial: str, placeholder: str) -> tk.StringVar:
            r = ctk.CTkFrame(row_frame, fg_color="transparent")
            r.pack(fill="x", padx=8, pady=(2, 2))
            ctk.CTkLabel(r, text=label_text, width=110, anchor="w",
                         font=ctk.CTkFont(size=11)).pack(side="left")
            var = tk.StringVar(value=initial)
            ctk.CTkEntry(r, textvariable=var, height=30,
                         placeholder_text=placeholder).pack(
                side="left", fill="x", expand=True, padx=(4, 4))
            ctk.CTkButton(
                r, text="...", width=34, height=30,
                command=lambda v=var: v.set(filedialog.askdirectory(parent=self) or v.get()),
            ).pack(side="right")
            return var

        src_var = _folder_entry(outer, "Eingangsordner:", source, "Pflicht…")
        tgt_var = _folder_entry(outer, "Ausgangsordner:", target, "Leer = im Eingangsordner…")

        ctk.CTkFrame(outer, height=4, fg_color="transparent").pack()

        entry[1] = src_var
        entry[2] = tgt_var

    def _remove_profile_row(self, entry: list):
        if entry in self._profile_rows:
            self._profile_rows.remove(entry)
        entry[3].destroy()

    # ------------------------------------------------------------------ Modell

    def _model_section(self, parent: ctk.CTkFrame):
        self._model_keys = {m: config.get_model_key(m) for m in config.KEY_MODELS}
        self._current_model = self.cfg.get("active_model", "rules")
        if self._current_model not in _MODEL_DISPLAY:
            self._current_model = "rules"

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
        self._om_active_model.set(_MODEL_DISPLAY[self._current_model])
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
        if m not in self._model_keys:
            return
        # Direkt vom Entry-Widget lesen (zuverlässiger als StringVar + show='*')
        entry = getattr(self, f"_entry_{m}", None)
        if entry:
            try:
                if not entry.winfo_exists():
                    return
            except Exception:
                return
            self._live_capture_key(m, entry)

    def _edit_model_key(self, model_key: str):
        """'Ändern' geklickt: Key in _model_keys löschen, Eingabefeld anzeigen."""
        self._model_keys[model_key] = ""
        self._rebuild_model_detail(self._current_model)

    def _delete_model_key(self, model_key: str):
        """Key dauerhaft aus Credential Manager löschen."""
        label = _MODEL_DISPLAY.get(model_key, model_key)
        if messagebox.askyesno(
            "API-Key löschen",
            f"Den gespeicherten API-Key für\n{label}\nwirklich löschen?",
            parent=self,
        ):
            self._model_keys[model_key] = ""
            config.set_model_key(model_key, "")
            self._rebuild_model_detail(self._current_model)

    def _save_key_immediately(self, model_key: str, entry) -> None:
        """'✓ Schlüssel speichern' geklickt: Key direkt aus Entry lesen und
        sofort in den Windows Credential Manager schreiben. Umgeht alle
        FocusOut/Placeholder-Probleme des Haupt-Speichern-Buttons."""
        val = self._entry_value(entry)
        if not val:
            messagebox.showwarning("Leer", "Bitte zuerst einen API-Key einfügen.", parent=self)
            return
        err = config.set_model_key(model_key, val)
        if err:
            messagebox.showerror("Fehler", f"Key konnte nicht gespeichert werden:\n{err}", parent=self)
            return
        self._model_keys[model_key] = val
        self._rebuild_model_detail(self._current_model)

    def _toggle_key_visibility(self, model_key: str):
        """Auge-Toggle: Key im Klartext oder maskiert anzeigen."""
        entry = getattr(self, f"_entry_{model_key}", None)
        btn   = getattr(self, f"_btn_eye_{model_key}", None)
        if not entry:
            return
        attr = f"_eye_visible_{model_key}"
        visible = not getattr(self, attr, False)
        setattr(self, attr, visible)
        entry.configure(show="" if visible else "*")
        if btn:
            btn.configure(text="\U0001f648" if visible else "\U0001f441")

    @staticmethod
    def _entry_value(entry) -> str:
        """Inhalt eines CTkEntry – leer, solange nur der Platzhalter steht."""
        if getattr(entry, "_placeholder_text_active", False):
            return ""
        try:
            raw = getattr(entry, "_entry", None)
            return (raw.get() if raw is not None else entry.get()).strip()
        except Exception:
            return ""

    def _live_capture_key(self, model_key: str, entry) -> None:
        """Liest den Key direkt aus dem Entry-Widget und speichert ihn sofort
        in _model_keys. Wird bei Tastendruck, Paste und FocusOut aufgerufen,
        damit der Wert unabhängig vom Haupt-Save-Button verfügbar ist."""
        val = self._entry_value(entry)
        if val:
            self._model_keys[model_key] = val

    # ------------------------------------------------ Modell-Details

    def _rebuild_model_detail(self, model_key: str):
        for w in self._model_detail_frame.winfo_children():
            w.destroy()
        p = self._model_detail_frame
        d = _MODEL_DETAIL.get(model_key, _MODEL_DETAIL["rules"])

        if model_key == "rules":
            self._info_label(p, f"  {d['info']}\n  {d['info2']}", d["color"])
            return

        if model_key == "ollama":
            self._labeled_entry(p, "Server", self._var_ollama_url,
                                f"Standard: {renamer.DEFAULT_OLLAMA_URL}  (auch z. B. 192.168.1.20:11434)")
            self._model_picker(p, self._var_ollama_model, "ollama")
        elif model_key == "custom":
            self._labeled_entry(p, "Basis-URL", self._var_custom_base_url,
                                "z. B. http://localhost:1234/v1")
            self._model_picker(p, self._model_id_vars["custom"], "custom")

        if d.get("key_label"):
            ctk.CTkLabel(p, text=d["key_label"], anchor="w",
                         font=ctk.CTkFont(size=11)).pack(fill="x", pady=(6, 2))
        self._key_widget(p, model_key)

        self._info_label(p, f"  {d['hint']}", theme.INFO, pady=(0, 0))
        self._info_label(p, f"  {d['warning']}", d["color"])

        if model_key in renamer.DEFAULT_MODEL_IDS:
            # Modell-ID optional ueberschreiben – falls ein Anbieter sein
            # Standardmodell abschaltet, ohne auf ein Update zu warten
            self._labeled_entry(p, "Modell-ID", self._model_id_vars[model_key],
                                f"Standard: {renamer.DEFAULT_MODEL_IDS[model_key]}")

        self._test_row(p)

    def _info_label(self, parent, text: str, color, pady=(0, 4)):
        ctk.CTkLabel(
            parent, text=text, font=ctk.CTkFont(size=10), text_color=color,
            anchor="w", justify="left", wraplength=460,
        ).pack(fill="x", pady=pady)

    def _labeled_entry(self, parent, label: str, var: tk.StringVar, placeholder: str):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(2, 4))
        ctk.CTkLabel(row, text=label, width=80, anchor="w",
                     font=ctk.CTkFont(size=11)).pack(side="left")
        ctk.CTkEntry(row, textvariable=var, height=30,
                     placeholder_text=placeholder).pack(side="left", fill="x", expand=True)

    def _model_picker(self, parent, var: tk.StringVar, kind: str):
        """Auswahlfeld mit den Modellen des Servers – Eintippen bleibt moeglich."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(2, 2))
        ctk.CTkLabel(row, text="Modell", width=80, anchor="w",
                     font=ctk.CTkFont(size=11)).pack(side="left")
        combo = ctk.CTkComboBox(row, variable=var, height=30,
                                values=[var.get()] if var.get() else [])
        combo.pack(side="left", fill="x", expand=True, padx=(0, 4))
        status = ctk.CTkLabel(parent, text="", font=ctk.CTkFont(size=10),
                              text_color=theme.MUTED, anchor="w", wraplength=460)
        ctk.CTkButton(
            row, text="↻ Laden", width=80, height=30,
            command=lambda: self._load_models(kind, combo, var, status),
        ).pack(side="left")
        status.pack(fill="x")
        # Beim Oeffnen gleich laden, wenn eine Adresse bekannt ist
        if kind == "ollama" or self._var_custom_base_url.get().strip():
            self.after(100, lambda: self._load_models(kind, combo, var, status))

    def _load_models(self, kind: str, combo, var: tk.StringVar, status):
        self._capture_current_model_key()
        key = self._model_keys.get(kind, "")
        url = (self._var_ollama_url if kind == "ollama" else self._var_custom_base_url).get()
        status.configure(text="Lade Modellliste …", text_color=theme.MUTED)

        def fetch():
            if kind == "ollama":
                return renamer.list_ollama_models(url, key)
            return renamer.list_compat_models(url, key)

        def show(models, error):
            if not combo.winfo_exists():
                return
            if error:
                status.configure(text=f"✗ {error}", text_color=theme.DANGER)
                return
            combo.configure(values=models)
            if models and var.get() not in models:
                var.set(models[0])
            text = f"✓ {len(models)} Modell(e) gefunden" if models else "Keine Modelle gefunden"
            if kind == "ollama" and not models:
                text += " – mit „ollama pull llama3.1“ eines laden"
            status.configure(text=text, text_color=theme.OK if models else theme.WARN)

        self._run_in_background(fetch, show)

    def _test_row(self, parent):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(8, 2))
        result = ctk.CTkLabel(parent, text="", font=ctk.CTkFont(size=10), anchor="w",
                              justify="left", wraplength=460, text_color=theme.MUTED)
        btn = ctk.CTkButton(row, text="Verbindung testen", width=160, height=30)
        btn.configure(command=lambda: self._test_connection(btn, result))
        btn.pack(side="left")
        ctk.CTkLabel(row, text="schickt einen erfundenen Beispielbrief",
                     font=ctk.CTkFont(size=10), text_color=theme.MUTED).pack(side="left", padx=(10, 0))
        result.pack(fill="x")

    def _ai_options(self) -> dict:
        """KI-Einstellungen aus den (noch nicht gespeicherten) Eingabefeldern."""
        self._capture_current_model_key()
        return {
            "model_keys": dict(self._model_keys),
            "model_ids": {m: v.get().strip() for m, v in self._model_id_vars.items() if v.get().strip()},
            "ollama_model": self._var_ollama_model.get().strip(),
            "ollama_url": self._var_ollama_url.get().strip(),
            "custom_base_url": self._var_custom_base_url.get().strip(),
        }

    def _test_connection(self, btn, result):
        opts = self._ai_options()
        model = self._current_model
        template = self._var_name_template.get().strip() or "{DATUM}_{ABSENDER}_{BETREFF}"
        date_format = self._om_date_format.get()
        space = "_" if self._om_space_replacement.get().startswith("_") else "-"
        btn.configure(state="disabled", text="Teste …")
        result.configure(text="", text_color=theme.MUTED)

        def run():
            return renamer.probe_provider(model, template, date_format, space, **opts)

        def show(value, error):
            if not btn.winfo_exists():
                return
            btn.configure(state="normal", text="Verbindung testen")
            if error:
                result.configure(text=f"✗ {error}", text_color=theme.DANGER)
            else:
                name, seconds = value
                result.configure(text=f"✓ Funktioniert ({seconds:.1f} s) → {name}.pdf",
                                 text_color=theme.OK)

        self._run_in_background(run, show)

    def _run_in_background(self, work, done):
        """work() im Hintergrund-Thread, done(ergebnis, fehler) danach im UI-Thread."""
        import threading
        box: dict = {}

        def worker():
            try:
                box["value"] = work()
            except Exception as e:
                box["error"] = str(e) or e.__class__.__name__

        def poll():
            if not self.winfo_exists():
                return
            if worker_thread.is_alive():
                self.after(150, poll)
                return
            done(box.get("value"), box.get("error"))

        worker_thread = threading.Thread(target=worker, daemon=True)
        worker_thread.start()
        self.after(150, poll)

    def _key_widget(self, p, model_key: str):
        existing_key = self._model_keys.get(model_key, "")

        if existing_key:
            # ── Schlüssel vorhanden: Masked-Preview-Zeile ──────────────
            key_row = ctk.CTkFrame(p, fg_color=theme.OK_BG, corner_radius=6)
            key_row.pack(fill="x", pady=(0, 4))

            ctk.CTkLabel(
                key_row,
                text=f"\U0001f511  {_mask_key(existing_key)}",
                font=ctk.CTkFont(size=11, family="Courier New"),
                text_color=theme.OK,
                anchor="w",
            ).pack(side="left", padx=(12, 0), pady=8)

            ctk.CTkButton(
                key_row, text="Löschen", width=78, height=28,
                fg_color="transparent", border_width=1,
                border_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
                text_color=theme.DANGER,
                command=lambda mk=model_key: self._delete_model_key(mk),
            ).pack(side="right", padx=(4, 8), pady=8)

            ctk.CTkButton(
                key_row, text="Ändern", width=78, height=28,
                fg_color="transparent", border_width=1, text_color=theme.TEXT,
                border_color=theme.BORDER, hover_color=theme.DIVIDER,
                command=lambda mk=model_key: self._edit_model_key(mk),
            ).pack(side="right", padx=(4, 0), pady=8)
            return

        # ── Kein Schlüssel: Eingabefeld anzeigen ──────────────────
        entry_row = ctk.CTkFrame(p, fg_color="transparent")
        entry_row.pack(fill="x", pady=(0, 4))

        entry = ctk.CTkEntry(
            entry_row, show="*", height=36,
            placeholder_text="API-Key einfügen  (Strg+V) ...",
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        if model_key not in ("ollama", "custom"):
            entry.focus()
        setattr(self, f"_entry_{model_key}", entry)

        # Echtzeit-Capture: Paste + Tippen landen sofort in _model_keys
        def _capture(event=None, mk=model_key, ew=entry):
            self.after(20, lambda: self._live_capture_key(mk, ew))

        entry.bind("<KeyRelease>", _capture)
        entry.bind("<<Paste>>", _capture)
        entry.bind("<FocusOut>", _capture)

        btn_eye = ctk.CTkButton(
            entry_row, text="\U0001f441", width=36, height=36,
            fg_color=theme.DIVIDER, hover_color=theme.HOVER_STRONG,
            command=lambda mk=model_key: self._toggle_key_visibility(mk),
        )
        btn_eye.pack(side="left", padx=(0, 4))
        setattr(self, f"_btn_eye_{model_key}", btn_eye)

        # Expliziter Speichern-Button: liest Entry direkt und schreibt in Keyring
        ctk.CTkButton(
            entry_row, text="✓ Schlüssel speichern", height=36,
            fg_color=theme.SAVE_BG, hover_color=theme.SAVE_HOVER, text_color=theme.SAVE_TEXT,
            border_width=1, border_color=theme.SAVE_HOVER,
            command=lambda mk=model_key, ew=entry: self._save_key_immediately(mk, ew),
        ).pack(side="left")

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
            text="  Tokens: {DATUM}  {JAHR}  {MONAT}  {TAG}  {ABSENDER}  {BETREFF}  {ORIGINAL}\n"
                 "  \"/\" legt Unterordner an, z. B. {JAHR}/{MONAT}/{DATUM}_{ABSENDER}",
            font=ctk.CTkFont(size=10),
            text_color=theme.SUBTLE,
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

        preview_frame = ctk.CTkFrame(parent, fg_color=theme.SURFACE, corner_radius=8)
        preview_frame.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(
            preview_frame, text="Vorschau:",
            font=ctk.CTkFont(size=10), text_color=theme.MUTED, anchor="w",
        ).pack(side="left", padx=(12, 6), pady=10)
        self._preview_label = ctk.CTkLabel(
            preview_frame, text="",
            font=ctk.CTkFont(size=11, family="Courier New"),
            text_color=theme.ACCENT_TEXT, anchor="w",
        )
        self._preview_label.pack(side="left", fill="x", expand=True, padx=(0, 12), pady=10)

        self._var_name_template.trace_add("write", lambda *_: self._update_preview())
        self._update_preview()

    def _update_preview(self):
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
            text_color=theme.SUBTLE,
            anchor="w",
        ).pack(fill="x", pady=(0, 8))

        self._sender_rows_frame = tk.Frame(parent, background=theme.resolve(theme.BG), bd=0, highlightthickness=0)
        self._sender_rows_frame.pack(fill="x")

        self._sender_rows: list[tuple] = []

        for key, val in self.cfg.get("custom_senders", {}).items():
            self._add_sender_row(key, val)

        ctk.CTkButton(
            parent,
            text="+ Eintrag hinzufügen",
            height=32,
            fg_color="transparent",
            text_color=theme.TEXT,
            border_width=1,
            border_color=theme.BORDER,
            hover_color=theme.DIVIDER,
            command=lambda: self._add_sender_row("", ""),
        ).pack(anchor="w", pady=(6, 0))

    def _add_sender_row(self, key: str = "", value: str = ""):
        row = ctk.CTkFrame(self._sender_rows_frame, fg_color=theme.SURFACE, corner_radius=8)
        row.pack(fill="x", pady=(0, 4))

        kv = tk.StringVar(value=key)
        vv = tk.StringVar(value=value)

        ctk.CTkEntry(
            row, textvariable=kv, height=32, placeholder_text="Suchbegriff…"
        ).pack(side="left", fill="x", expand=True, padx=(8, 4), pady=6)

        ctk.CTkLabel(row, text="→", text_color=theme.MUTED, width=20).pack(side="left", padx=2)

        ctk.CTkEntry(
            row, textvariable=vv, height=32, placeholder_text="Anzeigename…"
        ).pack(side="left", fill="x", expand=True, padx=(4, 4), pady=6)

        entry = (kv, vv, row)
        self._sender_rows.append(entry)

        ctk.CTkButton(
            row, text="✕", width=32, height=32,
            fg_color="transparent", hover_color=theme.DANGER_HOVER, text_color=theme.DANGER,
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
            text_color=theme.SUBTLE,
            anchor="w",
        ).pack(fill="x", pady=(0, 8))

        self._doc_type_rows_frame = tk.Frame(parent, background=theme.resolve(theme.BG), bd=0, highlightthickness=0)
        self._doc_type_rows_frame.pack(fill="x")

        self._doc_type_rows: list[tuple] = []

        for key, val in self.cfg.get("custom_doc_types", {}).items():
            self._add_doc_type_row(key, val)

        ctk.CTkButton(
            parent,
            text="+ Eintrag hinzufügen",
            height=32,
            fg_color="transparent",
            text_color=theme.TEXT,
            border_width=1,
            border_color=theme.BORDER,
            hover_color=theme.DIVIDER,
            command=lambda: self._add_doc_type_row("", ""),
        ).pack(anchor="w", pady=(6, 0))

    def _add_doc_type_row(self, key: str = "", value: str = ""):
        row = ctk.CTkFrame(self._doc_type_rows_frame, fg_color=theme.SURFACE, corner_radius=8)
        row.pack(fill="x", pady=(0, 4))

        kv = tk.StringVar(value=key)
        vv = tk.StringVar(value=value)

        ctk.CTkEntry(
            row, textvariable=kv, height=32, placeholder_text="Suchbegriff…"
        ).pack(side="left", fill="x", expand=True, padx=(8, 4), pady=6)

        ctk.CTkLabel(row, text="→", text_color=theme.MUTED, width=20).pack(side="left", padx=2)

        ctk.CTkEntry(
            row, textvariable=vv, height=32, placeholder_text="Anzeigename…"
        ).pack(side="left", fill="x", expand=True, padx=(4, 4), pady=6)

        entry = (kv, vv, row)
        self._doc_type_rows.append(entry)

        ctk.CTkButton(
            row, text="✕", width=32, height=32,
            fg_color="transparent", hover_color=theme.DANGER_HOVER, text_color=theme.DANGER,
            command=lambda t=entry: self._remove_doc_type_row(t),
        ).pack(side="right", padx=(0, 6), pady=6)

    def _remove_doc_type_row(self, entry_tuple: tuple):
        if entry_tuple in self._doc_type_rows:
            self._doc_type_rows.remove(entry_tuple)
        entry_tuple[2].destroy()

    # ------------------------------------------------- Watcher-Konfiguration

    def _watcher_section(self, parent: ctk.CTkFrame):
        ctk.CTkLabel(
            parent,
            text="Watcher-Konfiguration",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 8))

        # Dateitypen
        ctk.CTkLabel(
            parent, text="Dateitypen überwachen",
            font=ctk.CTkFont(size=11), anchor="w",
        ).pack(fill="x", pady=(0, 4))

        exts_frame = ctk.CTkFrame(parent, fg_color=theme.SURFACE, corner_radius=8)
        exts_frame.pack(fill="x", pady=(0, 8))

        current_exts = [e.lower() for e in self.cfg.get("watch_extensions", [".pdf"])]
        self._var_ext_pdf  = tk.BooleanVar(value=".pdf" in current_exts)
        self._var_ext_jpg  = tk.BooleanVar(value=".jpg" in current_exts or ".jpeg" in current_exts)
        self._var_ext_tiff = tk.BooleanVar(value=".tiff" in current_exts or ".tif" in current_exts)
        self._var_ext_png  = tk.BooleanVar(value=".png" in current_exts)

        for label, var in [
            ("PDF", self._var_ext_pdf), ("JPG/JPEG", self._var_ext_jpg),
            ("TIFF", self._var_ext_tiff), ("PNG", self._var_ext_png),
        ]:
            ctk.CTkCheckBox(
                exts_frame, text=label, variable=var, onvalue=True, offvalue=False,
                width=100,
            ).pack(side="left", padx=12, pady=10)

        # Namensmuster
        ctk.CTkLabel(
            parent, text="Namensmuster (Regex)",
            font=ctk.CTkFont(size=11), anchor="w",
        ).pack(fill="x", pady=(0, 4))
        self._var_name_pattern = tk.StringVar(value=self.cfg.get("name_pattern", ""))
        ctk.CTkEntry(
            parent, textvariable=self._var_name_pattern, height=36,
            placeholder_text=r"Leer = nur numerische Namen  (Bsp.: ^\d{6,}$ für mind. 6 Ziffern)",
        ).pack(fill="x", pady=(0, 8))

        # OCR Seiten + Stabilitäts-Timeout
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))

        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkLabel(left, text="OCR Seiten (max.)", font=ctk.CTkFont(size=11), anchor="w").pack(fill="x")
        self._om_ocr_max_pages = ctk.CTkOptionMenu(left, values=["1", "2", "3", "4", "5"], height=36)
        self._om_ocr_max_pages.set(str(self.cfg.get("ocr_max_pages", 2)))
        self._om_ocr_max_pages.pack(fill="x")

        right = ctk.CTkFrame(row, fg_color="transparent")
        right.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(right, text="Stabilitäts-Timeout (Sek.)", font=ctk.CTkFont(size=11), anchor="w").pack(fill="x")
        self._om_stability_timeout = ctk.CTkOptionMenu(
            right, values=["10", "20", "30", "60", "120"], height=36,
        )
        self._om_stability_timeout.set(str(self.cfg.get("stability_timeout", 30)))
        self._om_stability_timeout.pack(fill="x")

        # Duplikat-Strategie
        ctk.CTkLabel(
            parent, text="Duplikat-Strategie",
            font=ctk.CTkFont(size=11), anchor="w",
        ).pack(fill="x", pady=(8, 4))
        self._om_duplicate_strategy = ctk.CTkOptionMenu(
            parent,
            values=["Suffix hinzufügen (_2, _3 …)", "Überschreiben"],
            height=36,
        )
        strategy = self.cfg.get("duplicate_strategy", "suffix")
        self._om_duplicate_strategy.set(
            "Überschreiben" if strategy == "overwrite" else "Suffix hinzufügen (_2, _3 …)"
        )
        self._om_duplicate_strategy.pack(fill="x")

        # UNLESBAR_-Ordner
        ctk.CTkFrame(parent, height=6, fg_color="transparent").pack()
        self._folder_row(parent, "Ordner für unleserliche Dateien (optional)", "unlesbar_folder")
        ctk.CTkLabel(
            parent,
            text="  Leer = UNLESBAR_-Dateien bleiben im Eingangsordner",
            font=ctk.CTkFont(size=10), text_color=theme.SUBTLE, anchor="w",
        ).pack(fill="x", pady=(0, 4))

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
                filedialog.askdirectory(parent=self, initialdir=v.get() or "/") or v.get()
            ),
        ).pack(side="right")

        setattr(self, f"_var_{key}", var)

    def _check_update_now(self):
        from . import updater
        self._btn_check_now.configure(state="disabled", text="Prüfe…")
        self._lbl_check_result.configure(text="")
        channel = "beta" if self._om_update_channel.get().startswith("Beta") else "stable"
        result: dict = {}

        def _run():                      # Hintergrund-Thread: nur Netzwerk, kein Tk
            try:
                result["release"] = updater.fetch_latest(channel)
            except Exception as e:
                result["error"] = e
            result["done"] = True

        def _poll():                     # UI-Thread
            if not self.winfo_exists():
                return
            if "done" not in result:
                self.after(200, _poll)
                return
            self._btn_check_now.configure(state="normal", text="Jetzt auf Updates prüfen")
            release = result.get("release")
            if "error" in result:
                self._lbl_check_result.configure(text="Verbindungsfehler", text_color="#f44336")
            elif updater.is_newer(release, self.version):
                self._lbl_check_result.configure(text="")
                messagebox.showinfo(
                    "Update verfügbar",
                    f"Version {release['tag_name']} ist verfügbar!\n\nBitte starte Scan Watcher neu – "
                    "der Update-Dialog erscheint dann automatisch.",
                    parent=self,
                )
            else:
                self._lbl_check_result.configure(text=f"✓ Aktuell ({self.version})", text_color="#4caf50")

        import threading
        threading.Thread(target=_run, daemon=True).start()
        self.after(200, _poll)

    def _toggle_row(self, parent: ctk.CTkFrame, label: str, var: tk.BooleanVar):
        row = ctk.CTkFrame(parent, fg_color=theme.SURFACE, corner_radius=8)
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
        profiles = []
        for name_var, src_var, tgt_var, _ in getattr(self, "_profile_rows", []):
            src = src_var.get().strip() if src_var else ""
            if src:
                profiles.append({
                    "name": name_var.get().strip() or "Profil",
                    "source": src,
                    "target": tgt_var.get().strip() if tgt_var else "",
                })
        self.cfg["folder_profiles"] = profiles
        # Backward-compat: erstes Profil auch in source_folder schreiben
        self.cfg["source_folder"] = profiles[0]["source"] if profiles else ""
        self.cfg["target_folder"] = profiles[0]["target"] if profiles else ""

        self.cfg["autostart"]            = self._var_autostart.get()
        self.cfg["notifications"]        = self._var_notifications.get()
        self.cfg["log_level"]            = self._om_log_level.get()
        self.cfg["update_check_enabled"] = self._var_update_check.get()
        self.cfg["update_channel"]       = (
            "beta" if self._om_update_channel.get().startswith("Beta") else "stable"
        )
        self.cfg["telemetry_enabled"]    = self._var_telemetry.get()
        modes = {label: key for key, label in theme.APPEARANCE_MODES.items()}
        self.cfg["appearance_mode"]      = modes.get(self._om_appearance.get(), "dark")
        self.cfg["name_template"]     = self._var_name_template.get().strip() or "{DATUM}_{ABSENDER}_{BETREFF}"
        self.cfg["date_format"]       = self._om_date_format.get()
        sr = self._om_space_replacement.get()
        self.cfg["space_replacement"] = "_" if sr.startswith("_") else "-"

        # Aktives Modell + API-Keys
        # Keys gehen direkt in den Credential Manager (config.save() fasst sie
        # nicht an). Nur aus LEBENDIGEN Entry-Widgets mit echtem Inhalt lesen –
        # nach '✓ Schlüssel speichern' oder 'Löschen' ist das Entry ersetzt.
        self.cfg["active_model"] = _MODEL_ID.get(self._om_active_model.get(), "rules")
        self.cfg["model_ids"] = {
            m: v.get().strip() for m, v in self._model_id_vars.items() if v.get().strip()
        }
        for m in config.KEY_MODELS:
            entry = getattr(self, f"_entry_{m}", None)
            if entry is None:
                continue  # Kein Entry → Masked-Preview war von Anfang an aktiv → nicht anfassen
            try:
                alive = entry.winfo_exists()
            except Exception:
                alive = False
            if not alive:
                continue  # Entry-Widget wurde durch _save_key_immediately ersetzt → nicht anfassen
            # Entry lebendig: echter Inhalt oder Placeholder?
            if getattr(entry, "_placeholder_text_active", False):
                continue  # Placeholder aktiv → kein Key eingegeben → nicht anfassen
            try:
                raw = getattr(entry, "_entry", None)
                val = (raw.get() if raw is not None else entry.get()).strip()
            except Exception:
                val = ""
            if val:
                config.set_model_key(m, val)
        self.cfg["ollama_model"]    = self._var_ollama_model.get().strip()
        self.cfg["ollama_url"]      = renamer.normalize_ollama_url(self._var_ollama_url.get())
        self.cfg["custom_base_url"] = renamer.normalize_base_url(self._var_custom_base_url.get())

        missing = {
            "ollama": not self.cfg["ollama_model"] and "Bitte ein Ollama-Modell auswählen.",
            "custom": (not self.cfg["custom_base_url"] and "Bitte die Basis-URL des Endpunkts eintragen.")
                      or (not self.cfg["model_ids"].get("custom") and "Bitte ein Modell für den Endpunkt eintragen."),
        }.get(self.cfg["active_model"])
        if missing:
            messagebox.showerror("KI-Modell unvollständig", missing, parent=self)
            return

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

        # Watcher-Konfiguration
        exts = []
        if self._var_ext_pdf.get():   exts.append(".pdf")
        if self._var_ext_jpg.get():   exts.extend([".jpg", ".jpeg"])
        if self._var_ext_tiff.get():  exts.extend([".tiff", ".tif"])
        if self._var_ext_png.get():   exts.append(".png")
        self.cfg["watch_extensions"]   = exts or [".pdf"]
        pattern = self._var_name_pattern.get().strip()
        if pattern:
            try:
                re.compile(pattern)
            except re.error as e:
                messagebox.showerror(
                    "Ungültiges Namensmuster",
                    f"Das Namensmuster ist kein gültiger regulärer Ausdruck:\n{e}",
                    parent=self,
                )
                return
        self.cfg["name_pattern"]       = pattern
        self.cfg["ocr_max_pages"]      = int(self._om_ocr_max_pages.get())
        self.cfg["stability_timeout"]  = int(self._om_stability_timeout.get())
        ds = self._om_duplicate_strategy.get()
        self.cfg["duplicate_strategy"] = "overwrite" if ds == "Überschreiben" else "suffix"
        unlesbar_var = getattr(self, "_var_unlesbar_folder", None)
        self.cfg["unlesbar_folder"] = unlesbar_var.get().strip() if unlesbar_var else ""

        if not self.cfg.get("folder_profiles"):
            messagebox.showerror("Fehler", "Bitte mindestens einen Eingangsordner angeben.",
                                 parent=self)
            return

        config.save(self.cfg)
        self.result = self.cfg
        if self.on_save:
            self.on_save(self.cfg)
        self.destroy()

    def _export_settings(self):
        import json
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Alle Dateien", "*.*")],
            initialfile="scanwatcher_einstellungen.json",
            title="Einstellungen exportieren",
        )
        if not path:
            return
        to_export = {k: v for k, v in self.cfg.items() if not k.endswith("_key")}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(to_export, f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Exportiert", f"Einstellungen gespeichert:\n{path}", parent=self)
        except Exception as e:
            messagebox.showerror("Fehler", f"Export fehlgeschlagen:\n{e}", parent=self)

    # Nur Einstellungen uebernehmen – keine internen Zustandsfelder
    # (Einwilligung, Heartbeat, MOTD …) und keine unbekannten Schluessel.
    _IMPORT_SKIP = {"config_version", "telemetry_asked", "install_tracked",
                    "last_heartbeat", "last_motd_id", "autostart"}

    def _import_settings(self):
        import json
        path = filedialog.askopenfilename(
            parent=self,
            filetypes=[("JSON", "*.json"), ("Alle Dateien", "*.*")],
            title="Einstellungen importieren",
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Keine gültige Einstellungsdatei.")
        except Exception as e:
            messagebox.showerror("Fehler", f"Import fehlgeschlagen:\n{e}", parent=self)
            return
        imported = {
            k: v for k, v in data.items()
            if k in config.DEFAULT_CONFIG and k not in self._IMPORT_SKIP
            and isinstance(v, type(config.DEFAULT_CONFIG[k]))
        }
        merged = {**self.cfg, **imported}
        config.save(merged)
        if self.on_save:
            self.on_save(merged)
        messagebox.showinfo("Importiert", f"{len(imported)} Einstellungen importiert und gespeichert.",
                            parent=self)
        self.destroy()

    def _center(self):
        w, h = 520, 800
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        h = min(h, sh - 100)
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
