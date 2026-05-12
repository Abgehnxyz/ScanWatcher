"""
@file    updater.py
@project Scan Watcher
@company Nova Network
@date    Mai 2026
@brief   Update-Pruefung und In-App-Download via GitHub Releases API.
"""

import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import urllib.request
from typing import Callable

log = logging.getLogger("scan_watcher.updater")

_GITHUB_API_LATEST  = "https://api.github.com/repos/Abgehnxyz/ScanWatcher/releases/latest"
_GITHUB_API_ALL     = "https://api.github.com/repos/Abgehnxyz/ScanWatcher/releases"
_RELEASES_URL       = "https://github.com/Abgehnxyz/ScanWatcher/releases/latest"
_MOTD_URL           = "https://ops.abgehn.xyz/api/scanwatcher/motd"
_HEADERS            = {"Accept": "application/vnd.github+json", "User-Agent": "ScanWatcher"}


def _parse_version(tag: str) -> tuple[int, ...]:
    tag = tag.lstrip("vV")
    try:
        return tuple(int(x) for x in tag.split("."))
    except ValueError:
        return (0,)


def check_async(
    current_version: str,
    channel: str,
    on_update: Callable[[dict], None],
    enabled: bool = True,
) -> None:
    """Prueft im Hintergrund ob eine neuere Version verfuegbar ist."""
    if not enabled:
        return
    threading.Thread(
        target=_check,
        args=(current_version, channel, on_update),
        daemon=True,
    ).start()


def _check(current_version: str, channel: str, on_update: Callable[[dict], None]) -> None:
    try:
        if channel == "beta":
            req = urllib.request.Request(_GITHUB_API_ALL, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                releases = json.loads(resp.read().decode("utf-8"))
            release = releases[0] if releases else None
        else:
            req = urllib.request.Request(_GITHUB_API_LATEST, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                release = json.loads(resp.read().decode("utf-8"))

        if not release:
            return

        latest_tag = release.get("tag_name", "")
        if not latest_tag:
            return

        if _parse_version(latest_tag) > _parse_version(current_version):
            log.info(f"Update verfuegbar: {latest_tag}")
            on_update(release)
        else:
            log.debug(f"Kein Update (aktuell: {current_version}, latest: {latest_tag})")

    except Exception as e:
        log.debug(f"Update-Check fehlgeschlagen: {e}")


def download_installer(
    release: dict,
    on_progress: Callable[[int, int], None],
    on_done: Callable[[str | None, str], None],
) -> None:
    """
    Laedt den Installer aus den Release-Assets herunter.
    on_progress(bytes_done, bytes_total) – Fortschritt
    on_done(local_path, error_msg) – Fertig oder Fehler
    """
    threading.Thread(
        target=_download,
        args=(release, on_progress, on_done),
        daemon=True,
    ).start()


def _find_asset(release: dict, suffix: str) -> str | None:
    for asset in release.get("assets", []):
        name = asset.get("name", "")
        if name.lower().endswith(suffix.lower()):
            return asset.get("browser_download_url")
    return None


def _download(
    release: dict,
    on_progress: Callable[[int, int], None],
    on_done: Callable[[str | None, str], None],
) -> None:
    installer_url = _find_asset(release, ".exe")
    if not installer_url:
        on_done(None, "Kein Installer (.exe) im Release gefunden.")
        return

    sha256_url = _find_asset(release, ".sha256")
    expected_hash = None

    try:
        if sha256_url:
            with urllib.request.urlopen(sha256_url, timeout=10) as resp:
                expected_hash = resp.read().decode("utf-8").strip().split()[0].lower()
    except Exception as e:
        log.debug(f"SHA256-Datei nicht ladbar: {e}")

    try:
        tmp_dir = tempfile.mkdtemp(prefix="ScanWatcher_update_")
        tag = release.get("tag_name", "update").lstrip("vV")
        dest = os.path.join(tmp_dir, f"ScanWatcher_Setup_{tag}.exe")

        req = urllib.request.Request(installer_url, headers={"User-Agent": "ScanWatcher"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            done = 0
            sha = hashlib.sha256()
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    sha.update(chunk)
                    done += len(chunk)
                    on_progress(done, total)

        if expected_hash:
            actual = sha.hexdigest().lower()
            if actual != expected_hash:
                on_done(None, f"SHA256-Prüfung fehlgeschlagen.\nErwartet: {expected_hash}\nErhalten: {actual}")
                return

        on_done(dest, "")

    except Exception as e:
        on_done(None, str(e))


def run_installer_and_quit(installer_path: str) -> None:
    """Startet den Installer und beendet die App."""
    try:
        subprocess.Popen([installer_path], shell=False)
    except Exception as e:
        log.error(f"Installer konnte nicht gestartet werden: {e}")
        return
    sys.exit(0)


def check_motd_async(
    last_motd_id: str,
    on_motd: Callable[[str, str], None],
) -> None:
    """Prueft MOTD-Endpoint. on_motd(id, message) wenn neue Nachricht vorhanden."""
    threading.Thread(
        target=_check_motd,
        args=(last_motd_id, on_motd),
        daemon=True,
    ).start()


def _check_motd(last_motd_id: str, on_motd: Callable[[str, str], None]) -> None:
    try:
        req = urllib.request.Request(
            _MOTD_URL, headers={"User-Agent": "ScanWatcher"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        motd_id = data.get("id", "")
        message = data.get("message", "")
        if motd_id and message and motd_id != last_motd_id:
            on_motd(motd_id, message)
    except Exception as e:
        log.debug(f"MOTD-Check fehlgeschlagen: {e}")
