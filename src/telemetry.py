"""
@file    telemetry.py
@project Scan Watcher
@company Nova Network GmbH
@date    Mai 2026
@brief   Anonymes Opt-in Telemetrie-Modul.
         Sendet nur bei expliziter Zustimmung des Nutzers.
         Keine personenbezogenen Daten (kein Name, kein Hostname, keine IP).
"""

import json
import logging
import platform
import threading
import urllib.request
import uuid
from pathlib import Path

from . import config

log = logging.getLogger("scan_watcher.telemetry")

_ENDPOINT = "https://ops.abgehn.xyz/api/scanwatcher/event"
_TIMEOUT  = 10


def _get_install_id() -> str:
    """Erzeugt oder lädt eine anonyme lokale UUID (kein Personenbezug)."""
    id_file = config.CONFIG_DIR / "install_id"
    if id_file.exists():
        return id_file.read_text(encoding="utf-8").strip()
    new_id = str(uuid.uuid4())
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    id_file.write_text(new_id, encoding="utf-8")
    return new_id


def _send(payload: dict) -> None:
    """Sendet Event asynchron – Fehler werden still ignoriert."""
    def _post():
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                _ENDPOINT,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=_TIMEOUT):
                pass
        except Exception as e:
            log.debug(f"Telemetrie: {e}")

    threading.Thread(target=_post, daemon=True).start()


def _win_build() -> str:
    try:
        return platform.version().split(".")[2]  # Build-Nummer aus "10.0.22000"
    except Exception:
        return ""


def track_install(version: str) -> None:
    cfg = config.load()
    if not cfg.get("telemetry_enabled", False):
        return
    _send({
        "install_id": _get_install_id(),
        "event":      "install",
        "version":    version,
        "win_build":  _win_build(),
    })


def track_rename(model_used: str, success: bool) -> None:
    cfg = config.load()
    if not cfg.get("telemetry_enabled", False):
        return
    _send({
        "install_id": _get_install_id(),
        "event":      "rename",
        "model_used": model_used,
        "rename_ok":  success,
    })


def track_heartbeat(version: str, files_total: int) -> None:
    cfg = config.load()
    if not cfg.get("telemetry_enabled", False):
        return
    _send({
        "install_id":  _get_install_id(),
        "event":       "heartbeat",
        "version":     version,
        "files_total": files_total,
    })
