"""
@file    config.py
@project Scan Watcher
@company Nova Network
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


CONFIG_VERSION = 2

DEFAULT_CONFIG = {
    "config_version": CONFIG_VERSION,
    "source_folder": "",
    "target_folder": "",
    "tesseract_exe": "tesseract/tesseract.exe",
    "autostart": False,
    "notifications": True,
    "log_level": "INFO",
    "ollama_model": "llama3.2",
    "telemetry_enabled": False,
    "name_template": "{DATUM}_{ABSENDER}_{BETREFF}",
    "date_format": "YYYY-MM-DD",
    "space_replacement": "-",
    "active_model": "rules",
    "telemetry_asked": False,
    "last_heartbeat": "",
    "custom_senders": {},
    "custom_doc_types": {},
    "watch_extensions": [".pdf"],
    "name_pattern": "",
    "ocr_max_pages": 2,
    "stability_timeout": 30,
    "duplicate_strategy": "suffix",
    "folder_profiles": [],
}

CONFIG_DIR = Path(os.environ.get("APPDATA", "~")) / "ScanWatcher"
CONFIG_FILE = CONFIG_DIR / "config.json"
_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_NAME = "ScanWatcher"

_SERVICE = "ScanWatcher_NovaNetwork"

# Keyring-Account-Namen pro Anbieter (claude bleibt backward-kompatibel)
_KEY_ACCOUNTS = {
    "claude":  "anthropic_api_key",
    "openai":  "openai_api_key",
    "gemini":  "gemini_api_key",
    "mistral": "mistral_api_key",
    "groq":    "groq_api_key",
}


def get_model_key(model: str) -> str:
    """API-Key eines Anbieters sicher aus dem Windows Credential Manager laden."""
    account = _KEY_ACCOUNTS.get(model, "")
    if not account:
        return ""
    try:
        return keyring.get_password(_SERVICE, account) or ""
    except Exception:
        return ""


def set_model_key(model: str, key: str) -> None:
    """API-Key eines Anbieters sicher im Windows Credential Manager speichern."""
    account = _KEY_ACCOUNTS.get(model, "")
    if not account:
        return
    try:
        if key:
            keyring.set_password(_SERVICE, account, key)
        else:
            try:
                keyring.delete_password(_SERVICE, account)
            except Exception:
                pass
    except Exception:
        pass


# Backward-Compat-Aliase (alter Code nutzte anthropic_key direkt)
def get_anthropic_key() -> str:
    return get_model_key("claude")

def set_anthropic_key(key: str) -> None:
    set_model_key("claude", key)


def load() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    else:
        data = {}

    # Migration: active_model aus alten Feldern ableiten
    if "active_model" not in data:
        old_claude_key = get_model_key("claude")
        if data.get("ollama_enabled"):
            data["active_model"] = "ollama"
        elif old_claude_key or data.get("anthropic_key"):
            data["active_model"] = "claude"
        # else: DEFAULT_CONFIG liefert "rules"

    # Migration: alter anthropic_key aus JSON → Credential Manager
    if data.get("anthropic_key"):
        if not get_model_key("claude"):
            set_model_key("claude", data["anthropic_key"])
        del data["anthropic_key"]

    # Migration: source_folder/target_folder → folder_profiles
    if not data.get("folder_profiles") and data.get("source_folder"):
        data["folder_profiles"] = [{
            "name": "Standard",
            "source": data["source_folder"],
            "target": data.get("target_folder", ""),
        }]

    cfg = {**DEFAULT_CONFIG, **data}
    cfg["config_version"] = CONFIG_VERSION  # immer auf aktueller Version halten

    # Alle Model-Keys aus Credential Manager laden
    for model in _KEY_ACCOUNTS:
        cfg[f"{model}_key"] = get_model_key(model)

    return cfg


def save(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Alle API-Keys sicher speichern – nicht in JSON
    for model in _KEY_ACCOUNTS:
        key_field = f"{model}_key"
        if key_field in cfg:
            set_model_key(model, cfg.get(key_field, ""))
    # Nicht-serialisierbare Felder ausschliessen
    to_save = {k: v for k, v in cfg.items() if not k.endswith("_key")}
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
