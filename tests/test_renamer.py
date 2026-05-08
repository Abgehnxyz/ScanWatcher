"""
Tests fuer renamer.py
Ausfuehren: py -m pytest tests/
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.renamer import (
    apply_template, clean, unique_path,
    _extract_date, _extract_sender, _extract_subject,
    _format_date, _via_rules,
)


# ------------------------------------------------------------------ clean()

def test_clean_umlaute():
    assert clean("Württemberg") == "Wuerttemberg"
    assert clean("Straße") == "Strasse"
    assert clean("Köln / Bonn") == "Koeln-Bonn"


def test_clean_sonderzeichen():
    assert clean("Az. 2 O 383/25") == "Az-2-O-383-25"
    assert "--" not in clean("test--name")


def test_clean_underscore_replacement():
    assert clean("Nova Network", "_") == "Nova_Network"


# --------------------------------------------------------------- _format_date()

def test_format_date_iso():
    assert _format_date("2026-05-08", "YYYY-MM-DD") == "2026-05-08"


def test_format_date_german():
    assert _format_date("2026-05-08", "DD.MM.YYYY") == "08.05.2026"


def test_format_date_compact():
    assert _format_date("2026-05-08", "YYYYMMDD") == "20260508"


def test_format_date_invalid_passthrough():
    assert _format_date("unbekannt", "YYYY-MM-DD") == "unbekannt"


# ------------------------------------------------------------ apply_template()

def test_apply_template_default():
    result = apply_template(
        "{DATUM}_{ABSENDER}_{BETREFF}",
        "2026-05-08", "Nova Network", "Lizenz Rechnung",
    )
    assert result == "2026-05-08_Nova-Network_Lizenz-Rechnung"


def test_apply_template_german_date():
    result = apply_template(
        "{DATUM}_{ABSENDER}_{BETREFF}",
        "2026-05-08", "Nova Network", "Rechnung",
        date_format="DD.MM.YYYY",
    )
    assert result.startswith("08.05.2026")


def test_apply_template_year_month_day_tokens():
    result = apply_template(
        "{JAHR}/{MONAT}/{TAG}_{ABSENDER}",
        "2026-05-08", "Allianz", "Police",
    )
    assert "2026" in result
    assert "05" in result
    assert "08" in result


def test_apply_template_original_token():
    result = apply_template(
        "SCAN_{DATUM}_{ORIGINAL}",
        "2026-05-08", "Allianz", "Police",
        original_stem="20260508001",
    )
    assert "20260508001" in result


def test_apply_template_unknown_token_removed():
    result = apply_template("{DATUM}_{UNBEKANNT}", "2026-01-01", "X", "Y")
    assert "{UNBEKANNT}" not in result


def test_apply_template_max_length():
    long_betreff = "A" * 200
    result = apply_template("{DATUM}_{ABSENDER}_{BETREFF}", "2026-01-01", "X", long_betreff)
    assert len(result) <= 120


# ------------------------------------------------------------ _extract_date()

def test_extract_date_ddmmyyyy():
    assert _extract_date("Frankfurt, 22.04.2026\n", "202604220001.pdf") == "2026-04-22"


def test_extract_date_from_filename():
    assert _extract_date("kein datum hier", "202603150042.pdf") == "2026-03-15"


def test_extract_date_month_name():
    text = "Datum: 3. Mai 2026"
    assert _extract_date(text, "000.pdf") == "2026-05-03"


# ----------------------------------------------------------- _extract_sender()

def test_extract_sender_kravag():
    text = "KRAVAG-LOGISTIC Versicherungs-AG\nVoltastrasse 84"
    assert _extract_sender(text) == "KRAVAG"


def test_extract_sender_landgericht():
    text = "Landgericht Freiburg im Breisgau\nDatum: 07.04.2026"
    assert _extract_sender(text) == "Landgericht"


def test_extract_sender_custom_priority():
    text = "HUK-COBURG Rechnung"
    # custom_senders soll Vorrang haben
    assert _extract_sender(text, custom_senders={"huk-coburg": "MeinAnbieter"}) == "MeinAnbieter"


def test_extract_sender_custom_case_insensitive():
    text = "Nova Network GmbH"
    assert _extract_sender(text, custom_senders={"nova network": "NovaNet"}) == "NovaNet"


# ---------------------------------------------------------- _extract_subject()

def test_extract_subject_police():
    text = "KRAVAG-Logistic-Police Nr. 407 85 350295747 N\nBetriebsschutz"
    subj = _extract_subject(text)
    assert "Police" in subj and "407" in subj


def test_extract_subject_rechnung():
    text = "Rechnungsnummer: RE10154\nBetrag: 1.250,00 EUR"
    assert "Rechnung" in _extract_subject(text)


def test_extract_subject_custom_priority():
    text = "Wartungsvertrag Jahresrechnung"
    result = _extract_subject(text, custom_doc_types={"wartungsvertrag": "Wartung"})
    assert result == "Wartung"


def test_extract_subject_builtin_fallback():
    text = "Kündigung des Vertrages"
    assert _extract_subject(text) == "Kuendigung"


# ------------------------------------------------------------- unique_path()

def test_unique_path_new_file(tmp_path):
    p = unique_path(str(tmp_path), "test.pdf")
    assert p == str(tmp_path / "test.pdf")


def test_unique_path_suffix_strategy(tmp_path):
    (tmp_path / "test.pdf").write_text("x")
    p = unique_path(str(tmp_path), "test.pdf", "suffix")
    assert p == str(tmp_path / "test_2.pdf")


def test_unique_path_overwrite_strategy(tmp_path):
    existing = tmp_path / "test.pdf"
    existing.write_text("x")
    p = unique_path(str(tmp_path), "test.pdf", "overwrite")
    assert p == str(existing)


# -------------------------------------------------------------- _via_rules()

def test_via_rules_full_pipeline():
    text = "HUK-COBURG Versicherung\nDatum: 08.05.2026\nRechnung Nr. RE-99001"
    result = _via_rules(text, "20260508001.pdf")
    assert "2026" in result
    assert "HUK" in result or "Rechnung" in result


# ------------------------------------------------------ Mock: _via_ollama()

def test_via_ollama_success():
    from src.renamer import _via_ollama
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"response": "2026-05-08_TestFirma_Rechnung"}'
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = _via_ollama("OCR-Text", "001.pdf", "llama3.2")
    assert result == "2026-05-08_TestFirma_Rechnung"


def test_via_ollama_network_error():
    from src.renamer import _via_ollama
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        result = _via_ollama("OCR-Text", "001.pdf", "llama3.2")
    assert result is None


# ------------------------------------------------------ Mock: _via_claude()

def test_via_claude_success():
    from src.renamer import _via_claude
    mock_text = MagicMock()
    mock_text.text = "2026-05-08_Allianz_Police"
    mock_resp = MagicMock()
    mock_resp.content = [mock_text]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_resp

    with patch("anthropic.Anthropic", return_value=mock_client):
        result = _via_claude("OCR-Text", "001.pdf", "sk-ant-test")
    assert result == "2026-05-08_Allianz_Police"


def test_via_claude_api_error():
    from src.renamer import _via_claude
    with patch("anthropic.Anthropic", side_effect=Exception("unauthorized")):
        result = _via_claude("OCR-Text", "001.pdf", "bad-key")
    assert result is None
