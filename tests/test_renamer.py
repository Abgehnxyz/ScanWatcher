"""
Tests fuer renamer.py
Ausfuehren: py -m pytest tests/
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.renamer import clean, _extract_date, _extract_sender, _extract_subject


def test_clean_umlaute():
    assert clean("Württemberg") == "Wuerttemberg"
    assert clean("Straße") == "Strasse"
    assert clean("Köln / Bonn") == "Koeln-Bonn"


def test_clean_sonderzeichen():
    assert clean("Az. 2 O 383/25") == "Az-2-O-383-25"
    assert "--" not in clean("test--name")  # Keine Doppelbindestriche


def test_extract_date_ddmmyyyy():
    text = "Frankfurt, 22.04.2026\n\nSehr geehrte..."
    assert _extract_date(text, "202604220001.pdf") == "2026-04-22"


def test_extract_date_from_filename():
    assert _extract_date("kein datum hier", "202603150042.pdf") == "2026-03-15"


def test_extract_sender_kravag():
    text = "KRAVAG-LOGISTIC Versicherungs-AG\nVoltastrasse 84..."
    assert _extract_sender(text) == "KRAVAG"


def test_extract_sender_landgericht():
    text = "Landgericht Freiburg im Breisgau\nDatum: 07.04.2026"
    assert _extract_sender(text) == "Landgericht"


def test_extract_subject_police():
    text = "KRAVAG-Logistic-Police Nr. 407 85 350295747 N\nBetriebsschutz"
    subj = _extract_subject(text)
    assert "Police" in subj
    assert "407" in subj


def test_extract_subject_rechnung():
    text = "Rechnungsnummer: RE10154\nBetrag: 1.250,00 EUR"
    assert "Rechnung" in _extract_subject(text)


def test_extract_subject_fallback_dokumenttyp():
    text = "Sehr geehrte Damen und Herren,\nwir laden Sie zur Gueteverhandlung..."
    # Kein spezifisches Muster, aber "Gueteverhandlung" enthalten
    result = _extract_subject(text)
    assert result  # Sollte irgendetwas zurueckgeben
