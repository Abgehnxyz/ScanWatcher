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

import keyring


DEFAULT_CONFIG = {
    "source_folder": "",
    "target_folder": "",
    "tesseract_exe": "tesseract/tesseract.exe",
    "autostart": False,
    "notifications": True,
    "log_level": "INFO",
    "ollama_enabled": False,
    "ollama_model": "llama3.2",
}

CONFIG_DIR = Path(os.environ.get("APPDATA", "~")) / "ScanWatcher"
CONFIG_FILE = CONFIG_DIR / "config.json"
_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_NAME = "ScanWatcher"

_SERVICE = "ScanWatcher_NovaNetwork"
_ACCOUNT = "anthropic_api_key"


def get_anthropic_key() -> str:
    """API-Key sicher aus Windows Credential Manager laden."""
    try:
        return keyring.get_password(_SERVICE, _ACCOUNT) or ""
    except Exception:
        return ""


def set_anthropic_key(key: str) -> None:
    """API-Key sicher im Windows Credential Manager speichern."""
    try:
        if key:
            keyring.set_password(_SERVICE, _ACCOUNT, key)
        else:
            try:
                keyring.delete_password(_SERVICE, _ACCOUNT)
            except Exception:
                pass
    except Exception:
        pass


def load() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            cfg = {**DEFAULT_CONFIG, **data}
        except Exception:
            cfg = DEFAULT_CONFIG.copy()
    else:
        cfg = DEFAULT_CONFIG.copy()

    # API-Key: keyring hat Priorität; ggf. aus alter config.json migrieren
    keyring_key = get_anthropic_key()
    if keyring_key:
        cfg["anthropic_key"] = keyring_key
    elif cfg.get("anthropic_key"):
        # Einmalige Migration: Key aus JSON in Credential Manager überführen
        set_anthropic_key(cfg["anthropic_key"])
    else:
        cfg["anthropic_key"] = ""
    return cfg


def save(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # API-Key sicher speichern – nicht in JSON
    set_anthropic_key(cfg.get("anthropic_key", ""))
    to_save = {k: v for k, v in cfg.items() if k != "anthropic_key"}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, indent=2, ensure_ascii=False)
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
