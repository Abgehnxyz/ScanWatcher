"""
Tests fuer watcher.py – Pipeline, Doppelverarbeitung, Ueberschreiben.
Ausfuehren: py -m pytest tests/
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import ocr, telemetry, watcher

_TEXT = "Allianz Versicherungs-AG\nDatum: 08.05.2026\nIhre Police"


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    telemetry.configure(False)
    monkeypatch.setattr(watcher, "_wait_for_stable", lambda path, timeout=30: True)
    monkeypatch.setattr(watcher.config, "get_model_key", lambda m: "")
    watcher._claimed.clear()
    watcher._produced.clear()


def _ocr(text=_TEXT, conf=100.0):
    return lambda path, exe, pages=2: ocr.OcrResult(text=text, confidence=conf)


def _cfg(**kw):
    return {"tesseract_exe": "x", "active_model": "rules", **kw}


def test_pipeline_moves_into_template_subfolders(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr, "extract_text_with_confidence", _ocr())
    src = tmp_path / "in"; tgt = tmp_path / "out"
    src.mkdir(); tgt.mkdir()
    f = src / "20260508001.pdf"; f.write_bytes(b"%PDF")

    ok = watcher.process_file(str(f), _cfg(
        target_folder=str(tgt), name_template="{JAHR}/{MONAT}/{DATUM}_{ABSENDER}"))

    assert ok
    assert not f.exists()
    files = list(tgt.rglob("*.pdf"))
    assert len(files) == 1
    assert files[0].relative_to(tgt).parts[:2] == ("2026", "05")


def test_low_confidence_prefix_goes_on_filename_not_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr, "extract_text_with_confidence", _ocr(conf=20.0))
    f = tmp_path / "1.pdf"; f.write_bytes(b"%PDF")
    watcher.process_file(str(f), _cfg(name_template="{JAHR}/{DATUM}_{ABSENDER}"))
    [result] = list((tmp_path / "2026").glob("*.pdf"))
    assert result.name.startswith("PRUEFEN_2026-05-08_")


def test_overwrite_without_target_folder(tmp_path, monkeypatch):
    """Bug: os.rename wirft unter Windows FileExistsError, wenn das Ziel existiert."""
    monkeypatch.setattr(ocr, "extract_text_with_confidence", _ocr())
    f = tmp_path / "1.pdf"; f.write_bytes(b"neu")
    existing = tmp_path / "2026-05-08_Allianz-Versicherungs-AG_Versicherungspolice.pdf"
    existing.write_bytes(b"alt")

    ok = watcher.process_file(str(f), _cfg(duplicate_strategy="overwrite"))

    assert ok
    assert existing.read_bytes() == b"neu"
    assert not f.exists()


def test_suffix_strategy_keeps_both(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr, "extract_text_with_confidence", _ocr())
    f = tmp_path / "1.pdf"; f.write_bytes(b"neu")
    (tmp_path / "2026-05-08_Allianz-Versicherungs-AG_Versicherungspolice.pdf").write_bytes(b"alt")
    watcher.process_file(str(f), _cfg())
    assert (tmp_path / "2026-05-08_Allianz-Versicherungs-AG_Versicherungspolice_2.pdf").read_bytes() == b"neu"


def test_unreadable_goes_to_unlesbar_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr, "extract_text_with_confidence", _ocr(text="", conf=-1))
    f = tmp_path / "42.pdf"; f.write_bytes(b"%PDF")
    bad = tmp_path / "unlesbar"
    watcher.process_file(str(f), _cfg(unlesbar_folder=str(bad)))
    assert (bad / "UNLESBAR_42.pdf").exists()


def test_same_file_is_processed_only_once(tmp_path):
    """Startscan + Watchdog-Event (oder zwei Profile) dürfen nicht doppelt laufen."""
    p = str(tmp_path / "1.pdf")
    assert watcher._claim(p) is True
    assert watcher._claim(p) is False
    watcher._release(p)
    assert watcher._claim(p) is True


def test_own_output_is_ignored(tmp_path, monkeypatch):
    """Passt der neue Name wieder ins Namensmuster, darf keine Schleife entstehen."""
    monkeypatch.setattr(ocr, "extract_text_with_confidence", _ocr())
    f = tmp_path / "1.pdf"; f.write_bytes(b"%PDF")
    watcher.process_file(str(f), _cfg())
    [out] = list(tmp_path.glob("2026-*.pdf"))
    assert watcher._claim(str(out)) is False


def test_is_numeric_file():
    assert watcher.is_numeric_file("20260508001.pdf")
    assert not watcher.is_numeric_file("SCAN_1.pdf")
    assert watcher.is_numeric_file("SCAN_1.pdf", name_pattern=r"SCAN_\d+")
    assert not watcher.is_numeric_file("1.jpg")
