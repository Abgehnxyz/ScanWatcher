"""
@file    telemetry.py
@project Scan Watcher
@company Nova Network
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

from . import config

log = logging.getLogger("scan_watcher.telemetry")

_ENDPOINT = "https://ops.abgehn.xyz/api/scanwatcher/event"
_TIMEOUT  = 10

_enabled: bool | None = None   # None = noch nicht gesetzt -> aus config lesen


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


def configure(enabled: bool) -> None:
    """Einwilligung setzen – beim Start und nach jedem Speichern der Einstellungen."""
    global _enabled
    _enabled = bool(enabled)


def _is_enabled() -> bool:
    if _enabled is None:
        configure(config.load().get("telemetry_enabled", False))
    return bool(_enabled)


def track_install(version: str, cfg: dict) -> None:
    """Einmalig pro Installation senden (nicht bei jedem Start)."""
    if not _is_enabled() or cfg.get("install_tracked"):
        return
    _send({
        "install_id": _get_install_id(),
        "event":      "install",
        "version":    version,
        "win_build":  _win_build(),
    })
    cfg["install_tracked"] = True
    config.save(cfg)


def track_rename(model_used: str, success: bool) -> None:
    if not _is_enabled():
        return
    _send({
        "install_id": _get_install_id(),
        "event":      "rename",
        "model_used": model_used,
        "rename_ok":  success,
    })


def track_heartbeat(version: str, files_total: int) -> None:
    if not _is_enabled():
        return
    _send({
        "install_id":  _get_install_id(),
        "event":       "heartbeat",
        "version":     version,
        "files_total": files_total,
    })
