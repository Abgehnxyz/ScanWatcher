"""
Tests fuer updater.py – ohne Netzwerk.
Ausfuehren: py -m pytest tests/
"""

import hashlib
import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import updater


def _resp(body: bytes, headers=None) -> MagicMock:
    r = MagicMock()
    stream = io.BytesIO(body)
    r.read.side_effect = lambda n=-1: stream.read(n)
    r.headers = headers or {}
    r.__enter__ = lambda s: s
    r.__exit__ = MagicMock(return_value=False)
    return r


def _release(with_sha=True):
    assets = [{"name": "ScanWatcher_Setup_v9.9.9.exe", "browser_download_url": "https://x/setup.exe"}]
    if with_sha:
        assets.append({"name": "ScanWatcher_Setup_v9.9.9.exe.sha256", "browser_download_url": "https://x/sha"})
    return {"tag_name": "v9.9.9", "assets": assets}


def test_is_newer():
    assert updater.is_newer({"tag_name": "v1.0.20"}, "1.0.19")
    assert not updater.is_newer({"tag_name": "v1.0.19"}, "1.0.19")
    assert not updater.is_newer(None, "1.0.19")


def test_beta_picks_highest_non_draft():
    releases = [
        {"tag_name": "v2.0.0", "draft": True},
        {"tag_name": "v1.1.0-beta"},
        {"tag_name": "v1.2.0"},
    ]
    with patch("urllib.request.urlopen", return_value=_resp(json.dumps(releases).encode())):
        assert updater.fetch_latest("beta")["tag_name"] == "v1.2.0"


def test_download_refuses_without_checksum():
    result = {}
    updater._download(_release(with_sha=False), lambda d, t: None,
                      lambda path, err: result.update(path=path, err=err))
    assert result["path"] is None and "Prüfsumme" in result["err"]


def test_download_checks_hash(tmp_path):
    payload = b"installer-bytes"
    good = hashlib.sha256(payload).hexdigest()

    def fake_urlopen(req, timeout=0):
        url = req.full_url if hasattr(req, "full_url") else req
        if url.endswith("sha"):
            return _resp(f"{good}  setup.exe".encode())
        return _resp(payload, {"Content-Length": str(len(payload))})

    result = {}
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        updater._download(_release(), lambda d, t: None,
                          lambda path, err: result.update(path=path, err=err))
    assert result["err"] == "" and Path(result["path"]).read_bytes() == payload


def test_download_rejects_wrong_hash():
    def fake_urlopen(req, timeout=0):
        if req.full_url.endswith("sha"):
            return _resp(b"0" * 64)
        return _resp(b"manipuliert")

    result = {}
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        updater._download(_release(), lambda d, t: None,
                          lambda path, err: result.update(path=path, err=err))
    assert result["path"] is None and "SHA256" in result["err"]
