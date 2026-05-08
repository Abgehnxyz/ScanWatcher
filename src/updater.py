"""
@file    updater.py
@project Scan Watcher
@company Nova Network
@date    Mai 2026
@brief   Update-Pruefung via GitHub Releases API (GET /repos/.../releases/latest).
         Laeuft im Hintergrund, kein Blockieren des Tray.
"""

import json
import logging
import threading
import urllib.request
from typing import Callable

log = logging.getLogger("scan_watcher.updater")

_GITHUB_API = "https://api.github.com/repos/Abgehnxyz/ScanWatcher/releases/latest"
_RELEASES_URL = "https://github.com/Abgehnxyz/ScanWatcher/releases/latest"


def _parse_version(tag: str) -> tuple[int, ...]:
    """'v1.2.3' oder '1.2.3' → (1, 2, 3)."""
    tag = tag.lstrip("vV")
    try:
        return tuple(int(x) for x in tag.split("."))
    except ValueError:
        return (0,)


def check_async(current_version: str, on_update: Callable[[str, str], None]) -> None:
    """
    Prueft im Hintergrund ob eine neuere Version auf GitHub verfuegbar ist.
    on_update(latest_tag, release_url) wird im selben Thread aufgerufen.
    """
    threading.Thread(
        target=_check,
        args=(current_version, on_update),
        daemon=True,
    ).start()


def _check(current_version: str, on_update: Callable[[str, str], None]) -> None:
    try:
        req = urllib.request.Request(
            _GITHUB_API,
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "ScanWatcher"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        latest_tag = data.get("tag_name", "")
        html_url = data.get("html_url", _RELEASES_URL)

        if not latest_tag:
            return

        if _parse_version(latest_tag) > _parse_version(current_version):
            log.info(f"Update verfuegbar: {latest_tag}")
            on_update(latest_tag, html_url)
        else:
            log.debug(f"Kein Update (aktuell: {current_version}, latest: {latest_tag})")

    except Exception as e:
        log.debug(f"Update-Check fehlgeschlagen: {e}")
