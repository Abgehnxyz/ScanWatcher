"""
Tests fuer ocr.py – ohne echtes Tesseract.
Ausfuehren: py -m pytest tests/
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import ocr


def test_mean_confidence_accepts_floats():
    """Je nach Tesseract-/pytesseract-Version kommen Kommazahlen ("96.53") –
    "96.53".isdigit() ist False, die Werte duerfen nicht verloren gehen."""
    data = {"conf": ["-1", "96.53", 30.5, "-1", "abc"]}
    assert round(ocr._mean_confidence(data), 2) == 63.52
    assert ocr.needs_review(ocr.OcrResult("x", 30.0))
    assert not ocr.needs_review(ocr.OcrResult("x", -1))


def test_text_from_data_keeps_lines():
    data = {
        "text":      ["", "Allianz", "SE", "", "Rechnung", "Nr.", "4711"],
        "block_num": [1, 1, 1, 1, 2, 2, 2],
        "par_num":   [1, 1, 1, 1, 1, 1, 1],
        "line_num":  [1, 1, 1, 1, 1, 1, 1],
    }
    assert ocr._text_from_data(data) == "Allianz SE\nRechnung Nr. 4711"


def test_tiny_text_layer_triggers_ocr(monkeypatch):
    """Scanner-Fußzeile "Seite 1" als Textlayer darf die OCR nicht verhindern."""
    monkeypatch.setattr(ocr, "_try_pdfplumber", lambda p, n: "Seite 1")
    long_text = "Allianz Versicherungs-AG\nIhre Police 4711 vom 08.05.2026"
    monkeypatch.setattr(ocr, "_try_ocr", lambda p, exe, n: ocr.OcrResult(long_text, 88.0))
    result = ocr.extract_text_with_confidence("x.pdf", "tess")
    assert result.text == long_text and result.confidence == 88.0


def test_real_text_layer_skips_ocr(monkeypatch):
    layer = "Rechnung Nr. 4711 vom 08.05.2026 – Allianz Versicherungs-AG, Musterstadt"
    monkeypatch.setattr(ocr, "_try_pdfplumber", lambda p, n: layer)

    def boom(*a):
        raise AssertionError("OCR darf nicht laufen")
    monkeypatch.setattr(ocr, "_try_ocr", boom)
    assert ocr.extract_text_with_confidence("x.pdf", "tess").confidence == 100.0
