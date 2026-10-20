"""
@file    config.py
@project Scan Watcher
@company Nova Network
@date    Mai 2026
@brief   Konfigurationsverwaltung – laedt und speichert Einstellungen
         unter %%APPDATA%%\\ScanWatcher\\config.json, verwaltet Autostart-Registry.
         API-Keys liegen ausschliesslich im Windows Credential Manager und
         werden nur ueber get_model_key()/set_model_key() gelesen/geschrieben.
"""

import json
import os
import sys
import winreg
from pathlib import Path

import keyring


CONFIG_VERSION = 3

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
    "model_ids": {},
    "telemetry_asked": False,
    "install_tracked": False,
    "last_heartbeat": "",
    "custom_senders": {},
    "custom_doc_types": {},
    "watch_extensions": [".pdf"],
    "name_pattern": "",
    "ocr_max_pages": 2,
    "stability_timeout": 30,
    "duplicate_strategy": "suffix",
    "folder_profiles": [],
    "appearance_mode": "dark",
    "unlesbar_folder": "",
    "update_channel": "stable",
    "update_check_enabled": True,
    "last_motd_id": "",
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
KEY_MODELS = tuple(_KEY_ACCOUNTS)


def get_model_key(model: str) -> str:
    """API-Key eines Anbieters sicher aus dem Windows Credential Manager laden."""
    account = _KEY_ACCOUNTS.get(model, "")
    if not account:
        return ""
    try:
        return keyring.get_password(_SERVICE, account) or ""
    except Exception:
        return ""


def set_model_key(model: str, key: str) -> str | None:
    """API-Key eines Anbieters sicher im Windows Credential Manager speichern.
    Leerer Key loescht den Eintrag.
    Gibt None bei Erfolg zurück, oder eine Fehlermeldung als String."""
    account = _KEY_ACCOUNTS.get(model, "")
    if not account:
        return None
    try:
        if key:
            keyring.set_password(_SERVICE, account, key)
        else:
            try:
                keyring.delete_password(_SERVICE, account)
            except Exception:
                pass
    except Exception as exc:
        return str(exc)
    return None


def _strip_secrets(cfg: dict) -> dict:
    """Entfernt alle *_key-Felder – Keys gehoeren nie in config.json."""
    return {k: v for k, v in cfg.items() if not k.endswith("_key")}


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
        if data.get("ollama_enabled"):
            data["active_model"] = "ollama"
        elif data.get("anthropic_key") or get_model_key("claude"):
            data["active_model"] = "claude"
        # else: DEFAULT_CONFIG liefert "rules"

    # Migration: alter anthropic_key aus JSON → Credential Manager
    if data.get("anthropic_key"):
        if not get_model_key("claude"):
            set_model_key("claude", data["anthropic_key"])

    # Migration: source_folder/target_folder → folder_profiles
    if not data.get("folder_profiles") and data.get("source_folder"):
        data["folder_profiles"] = [{
            "name": "Standard",
            "source": data["source_folder"],
            "target": data.get("target_folder", ""),
        }]

    cfg = {**DEFAULT_CONFIG, **_strip_secrets(data)}
    cfg["config_version"] = CONFIG_VERSION  # immer auf aktueller Version halten

    # Autostart: Die Registry ist die Wahrheit (der Installer setzt den Eintrag,
    # ohne config.json zu kennen). Sonst wuerde das erste save() ihn loeschen.
    cfg["autostart"] = is_autostart_enabled()

    return cfg


def save(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_strip_secrets(cfg), f, indent=2, ensure_ascii=False)
    os.replace(tmp, CONFIG_FILE)
    _apply_autostart(cfg.get("autostart", False))


def get_log_path() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR / "scan_watcher.log"


def _autostart_command() -> str:
    """Startbefehl fuer den Run-Key – EXE im Build, pythonw + run.py in der Entwicklung."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    exe = pythonw if pythonw.exists() else Path(sys.executable)
    run_py = Path(__file__).resolve().parent.parent / "run.py"
    return f'"{exe}" "{run_py}"'


def is_autostart_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY) as key:
            winreg.QueryValueEx(key, _REG_NAME)
        return True
    except OSError:
        return False


def _apply_autostart(enabled: bool) -> None:
    """Autostart-Eintrag setzen oder entfernen – nur bei tatsaechlicher Aenderung,
    damit ein vorhandener Installer-Eintrag nicht ueberschrieben wird."""
    try:
        if enabled == is_autostart_enabled():
            return
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, _REG_NAME, 0, winreg.REG_SZ, _autostart_command())
            else:
                winreg.DeleteValue(key, _REG_NAME)
    except OSError:
        pass
