"""
@file    config.py
@project Scan Watcher
@company Nova Network GmbH
@date    Mai 2026
@brief   Konfigurationsverwaltung – laedt und speichert Einstellungen
         unter %%APPDATA%%\ScanWatcher\config.json, verwaltet Autostart-Registry.
"""

import json
import os
import sys
import winreg
from pathlib import Path


DEFAULT_CONFIG = {
    "source_folder": "",
    "target_folder": "",
    "tesseract_exe": "tesseract/tesseract.exe",
    "anthropic_key": "",
    "autostart": False,
    "notifications": True,
    "log_level": "INFO",
}

CONFIG_DIR = Path(os.environ.get("APPDATA", "~")) / "ScanWatcher"
CONFIG_FILE = CONFIG_DIR / "config.json"
_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_NAME = "ScanWatcher"


def load() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            return {**DEFAULT_CONFIG, **data}
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    _apply_autostart(cfg.get("autostart", False))


def get_log_path() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR / "scan_watcher.log"


def _apply_autostart(enabled: bool) -> None:
    """Autostart-Eintrag in der Windows-Registry setzen oder entfernen."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_KEY,
            0, winreg.KEY_SET_VALUE
        )
        if enabled:
            exe = sys.executable if getattr(sys, "frozen", False) else sys.executable
            winreg.SetValueEx(key, _REG_NAME, 0, winreg.REG_SZ, f'"{exe}"')
        else:
            try:
                winreg.DeleteValue(key, _REG_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception:
        pass
