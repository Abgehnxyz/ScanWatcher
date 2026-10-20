"""
@file    theme.py
@project Scan Watcher
@company Nova Network
@date    Oktober 2026
@brief   Farbpalette fuer Hell- und Dunkelmodus. CTk-Widgets akzeptieren
         (hell, dunkel)-Tupel direkt; fuer reine tk-Widgets resolve() nutzen.
"""

from pathlib import Path

import customtkinter as ctk

BG           = ("#f3f4f8", "#141420")
HEADER       = ("#e2e5ee", "#0a0a14")
HEADER_ALT   = ("#e7e9f1", "#1a1a2e")
SURFACE      = ("#e6e8ef", "#1e1e2e")
DIVIDER      = ("#d4d7e0", "#2a2a3a")
HOVER_STRONG = ("#cfd2dc", "#3a3a4a")
BORDER       = ("#b8bcc8", "#444444")
BORDER_SOFT  = ("#c8ccd6", "#333333")
TEXT         = ("#1a1a24", "#ffffff")
TEXT_SOFT    = ("#3c4050", "#cccccc")
MUTED        = ("#5b6070", "#888888")
SUBTLE       = ("#6b7080", "#666666")
ACCENT_TEXT  = ("#1d5fa0", "#88ccff")
INFO         = ("#2a6db0", "#4488cc")
WARN         = ("#b35a10", "#e07020")
OK           = ("#2e7d32", "#55cc55")
OK_BG        = ("#e3f3e3", "#151f15")
DANGER       = ("#c62828", "#cc4444")
DANGER_HOVER = ("#f6dede", "#3a2a2a")
SAVE_BG      = ("#d9f0d9", "#1a4a1a")
SAVE_HOVER   = ("#c4e6c4", "#2a6a2a")
SAVE_TEXT    = ("#1b5e20", "#88ee88")
TAB_BAR      = ("#dfe2ea", "#1e1e2e")
TAB_SELECTED = ("#2d5a8e", "#2d5a8e")
TAB_HOVER    = ("#3a6fa8", "#3a6fa8")

GREEN_DOT = "#22c55e"
RED_DOT   = "#ef4444"
# Ko-fi-Blau leicht abgedunkelt – das Original (#29abe0) hat mit weisser
# Schrift nur 2,6:1 Kontrast
KOFI       = "#1b84b8"
KOFI_HOVER = "#156c97"

# Hellmodus-Akzent fuer Buttons/Auswahlmenues: CTk-Standard (#3B8ED0) hat mit
# weisser Schrift nur 2,7:1 Kontrast. Dunkelmodus bleibt beim CTk-Standard.
_ACCENT_LIGHT       = "#2464a8"
_ACCENT_LIGHT_HOVER = "#1c5189"

APPEARANCE_MODES = {"dark": "Dunkel", "light": "Hell", "system": "Wie Windows"}

ASSETS = Path(__file__).resolve().parent.parent / "assets"


def tune_default_theme() -> None:
    """Kontrast der Standard-Akzentfarbe im Hellmodus verbessern.
    Muss nach set_default_color_theme() und vor dem ersten Widget laufen."""
    t = ctk.ThemeManager.theme
    for widget, keys in {
        "CTkButton": ("fg_color", "hover_color"),
        "CTkOptionMenu": ("fg_color", "button_color", "button_hover_color"),
        "CTkSegmentedButton": ("selected_color", "selected_hover_color"),
    }.items():
        for key in keys:
            light = _ACCENT_LIGHT_HOVER if "hover" in key or key == "button_color" else _ACCENT_LIGHT
            t[widget][key] = [light, t[widget][key][1]]


def apply_appearance(mode: str) -> None:
    ctk.set_appearance_mode(mode if mode in APPEARANCE_MODES else "dark")


def resolve(color: tuple[str, str]) -> str:
    """Passende Farbe fuer reine tk-Widgets (Canvas, Frame) waehlen."""
    return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]


def prepare_window(win, title: str) -> None:
    """Titel, App-Icon und Vordergrund fuer ein neues Toplevel-Fenster."""
    win.title(title)
    win.configure(fg_color=BG)
    ico = ASSETS / "icon.ico"
    if ico.exists():
        # CTkToplevel setzt nach ~200 ms sein eigenes Icon – danach ueberschreiben
        win.after(250, lambda: win.winfo_exists() and win.iconbitmap(str(ico)))
    bring_to_front(win)


def bring_to_front(win) -> None:
    try:
        win.deiconify()
        win.lift()
        win.attributes("-topmost", True)
        win.after(300, lambda: win.winfo_exists() and win.attributes("-topmost", False))
        win.focus_force()
    except Exception:
        pass
