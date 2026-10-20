"""
Tests fuer renamer.py
Ausfuehren: py -m pytest tests/
"""

import ast
import collections
import io
import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.renamer import (
    BEKANNTE_BRANCHEN, apply_template, clean, determine_name,
    determine_name_with_source, unique_path,
    _extract_date, _extract_sender, _extract_subject,
    _format_date, _parse_fields, _via_rules,
    _extract_bewerber_name, _extract_bewerbung_stelle,
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

def test_extract_sender_volksbank_clean_line():
    # Firmenname ohne Adressdaten → vollständige Zeile wird verwendet
    text = "Volksbank Musterstadt eG\nIhr Anschreiben vom 01.01.2026"
    assert _extract_sender(text) == "Volksbank-Musterstadt-eG"


def test_extract_sender_volksbank_adresszeile():
    # Zeile mit Firmenname + Adressdaten → Adressfilter greift → kanonischer Kurzname
    text = "Volksbank Musterstadt eG . Postfach 100 . 12345 Musterstadt\nSehr geehrte Damen"
    assert _extract_sender(text) == "Volksbank"


def test_extract_sender_volksbank_im_fussbereich():
    # Briefkopf als eingebettetes Bild → pdfplumber liest ihn nicht.
    # Firmenname erscheint erst im Brieffuß nach Zeile 30.
    body = "\n".join([f"Zeile {i}" for i in range(35)])
    footer = "\nVolksbank Musterstadt eG | Musterstraße 1 | 12345 Musterstadt"
    text = body + footer
    assert _extract_sender(text) == "Volksbank"


def test_extract_sender_sparkasse_clean_line():
    # Sparkasse ohne Adressdaten → vollständige Zeile
    text = "Sparkasse Musterregion\nKontoinformation"
    assert _extract_sender(text) == "Sparkasse-Musterregion"


def test_extract_sender_kravag():
    # Vollständige Firmenzeile wird zurückgegeben (KRAVAG-LOGISTIC Versicherungs-AG hat " ag"-Suffix)
    text = "KRAVAG-LOGISTIC Versicherungs-AG\nVoltastrasse 84"
    assert _extract_sender(text) == "KRAVAG-LOGISTIC-Versicherungs-AG"


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


# --------------------------------------------------------- KI: Antworten

def _http_resp(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode("utf-8")
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _claude_resp(text: str, stop_reason: str = "end_turn") -> MagicMock:
    thinking = MagicMock(type="thinking")
    block = MagicMock(type="text", text=text)
    return MagicMock(stop_reason=stop_reason, content=[thinking, block])


_OCR = "HUK-COBURG Versicherung\nDatum: 08.05.2026\nRechnung Nr. RE-99001"
_FIELDS_JSON = '{"datum": "2026-05-08", "absender": "HUK Coburg", "betreff": "Rechnung"}'


def test_parse_fields_tolerates_code_fences():
    raw = "```json\n" + _FIELDS_JSON + "\n```"
    assert _parse_fields(raw) == {"datum": "2026-05-08", "absender": "HUK Coburg", "betreff": "Rechnung"}


def test_parse_fields_rejects_garbage():
    assert _parse_fields("") is None
    assert _parse_fields("2026-05-08_Firma_Rechnung") is None
    assert _parse_fields('{"datum": "", "absender": "", "betreff": ""}') is None


def test_ai_name_is_built_locally_from_template():
    with patch("urllib.request.urlopen", return_value=_http_resp({"response": _FIELDS_JSON})):
        name, used = determine_name_with_source(
            _OCR, "001.pdf", active_model="ollama",
            name_template="{JAHR}/{DATUM}_{ABSENDER}_{BETREFF}",
        )
    assert used == "ollama"
    assert name == "2026/2026-05-08_HUK-Coburg_Rechnung"


def test_ai_output_cannot_escape_target_folder():
    """Prompt-Injection im Brief: KI liefert Pfad-Tricks → werden entschärft."""
    evil = '{"datum": "2026-05-08", "absender": "..\\\\..\\\\Windows", "betreff": "../../x\\n:*?"}'
    with patch("urllib.request.urlopen", return_value=_http_resp({"response": evil})):
        name = determine_name(_OCR, "001.pdf", active_model="ollama")
    assert ".." not in name and "\\" not in name and "/" not in name
    assert ":" not in name and "\n" not in name


def test_ai_invalid_date_falls_back_to_rules_date():
    fields = '{"datum": "08.05.2026", "absender": "HUK", "betreff": "Rechnung"}'
    with patch("urllib.request.urlopen", return_value=_http_resp({"response": fields})):
        name = determine_name(_OCR, "001.pdf", active_model="ollama")
    assert name.startswith("2026-05-08_")


def test_custom_sender_overrides_ai():
    with patch("urllib.request.urlopen", return_value=_http_resp({"response": _FIELDS_JSON})):
        name = determine_name(_OCR, "001.pdf", active_model="ollama",
                              custom_senders={"huk-coburg": "Kfz-Versicherung"})
    assert "_Kfz-Versicherung_" in name


def test_ollama_network_error_falls_back_to_rules():
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        name, used = determine_name_with_source(_OCR, "20260508001.pdf", active_model="ollama")
    assert used == "rules"
    assert name.startswith("2026-05-08_")


def test_claude_uses_structured_output_and_current_model():
    client = MagicMock()
    client.messages.create.return_value = _claude_resp(_FIELDS_JSON)
    with patch("anthropic.Anthropic", return_value=client):
        name, used = determine_name_with_source(
            _OCR, "001.pdf", active_model="claude", model_keys={"claude": "sk-ant-test"},
        )
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-haiku-5-5"
    assert kwargs["output_config"]["format"]["type"] == "json_schema"
    assert kwargs["output_config"]["effort"] == "low"
    assert "temperature" not in kwargs        # Haiku 5.5: 400 bei temperature != 1
    assert used == "claude"
    assert name == "2026-05-08_HUK-Coburg_Rechnung"


def test_claude_model_id_override():
    client = MagicMock()
    client.messages.create.return_value = _claude_resp(_FIELDS_JSON)
    with patch("anthropic.Anthropic", return_value=client):
        determine_name(_OCR, "001.pdf", active_model="claude",
                       model_keys={"claude": "k"}, model_ids={"claude": "claude-sonnet-5-5"})
    assert client.messages.create.call_args.kwargs["model"] == "claude-sonnet-5-5"


def test_claude_refusal_falls_back_to_rules():
    client = MagicMock()
    client.messages.create.return_value = _claude_resp("", stop_reason="refusal")
    with patch("anthropic.Anthropic", return_value=client):
        _, used = determine_name_with_source(
            _OCR, "001.pdf", active_model="claude", model_keys={"claude": "k"},
        )
    assert used == "rules"


def test_claude_api_error_falls_back_to_rules():
    with patch("anthropic.Anthropic", side_effect=Exception("unauthorized")):
        _, used = determine_name_with_source(
            _OCR, "001.pdf", active_model="claude", model_keys={"claude": "bad"},
        )
    assert used == "rules"


def test_missing_key_uses_rules():
    _, used = determine_name_with_source(_OCR, "001.pdf", active_model="openai", model_keys={})
    assert used == "rules"


def test_openai_retries_without_json_mode_on_400():
    calls = []

    def fake_urlopen(req, timeout=0):
        body = json.loads(req.data)
        calls.append(body)
        if "response_format" in body:
            raise urllib.error.HTTPError(req.full_url, 400, "bad", {}, io.BytesIO(b"no json mode"))
        return _http_resp({"choices": [{"message": {"content": _FIELDS_JSON}}]})

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        _, used = determine_name_with_source(
            _OCR, "001.pdf", active_model="openai", model_keys={"openai": "sk-test"},
        )
    assert used == "openai"
    assert len(calls) == 2
    assert "max_completion_tokens" in calls[0]   # neue OpenAI-Modelle kennen max_tokens nicht


def test_gemini_key_in_header_not_url():
    seen = {}

    def fake_urlopen(req, timeout=0):
        seen["url"] = req.full_url
        seen["key"] = req.get_header("X-goog-api-key")
        return _http_resp({"candidates": [{"content": {"parts": [{"text": _FIELDS_JSON}]}}]})

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        _, used = determine_name_with_source(
            _OCR, "001.pdf", active_model="gemini", model_keys={"gemini": "AIza-secret"},
        )
    assert used == "gemini"
    assert "AIza-secret" not in seen["url"]
    assert seen["key"] == "AIza-secret"
    assert "gemini-1.5" not in seen["url"]


# ------------------------------------------------- Bewerbungs-Erkennung ----

# Realitätsnaher, frei erfundener OCR-Text (keine echten Personendaten!)
_BEWERBUNG_TEXT = """\
Mustermann Max
Beispielweg 12
12345 Musterstadt
Tel. 0123 4567890
max.mustermann@example.com

Beispiel Autohaus GmbH & Co. KG
Industriestraße 7
12345 Musterstadt

Musterstadt, 14. April 2026

Bewerbung um einen Ausbildungsplatz als Karosserie- und Fahrzeugbaumechaniker

Sehr geehrte Damen und Herren,

mit großem Interesse habe ich Ihre Stellenanzeige gelesen.
Ich interessiere mich sehr für Fahrzeuge und handwerkliche Tätigkeiten.
Teamarbeit ist für mich selbstverständlich, gleichzeitig arbeite ich auch eigenständig.

Mit freundlichen Grüßen

Max Mustermann
"""


def test_bewerbung_sender_aus_signatur():
    """Name wird aus dem Unterschriftsblock nach der Grußformel extrahiert."""
    lines = [l.strip() for l in _BEWERBUNG_TEXT.split("\n") if l.strip()]
    name = _extract_bewerber_name(lines)
    assert name == "Max-Mustermann"


def test_bewerbung_sender_aus_absenderblock():
    """Fallback: Name aus der ersten Zeile des Dokuments (Absenderblock oben)."""
    text = "Lena Müller\nHauptstraße 1\n12345 Berlin\n\nBewerbung als Entwicklerin"
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    name = _extract_bewerber_name(lines)
    assert name == "Lena-Mueller"


def test_bewerbung_stelle_aus_betreff():
    """Stellenbezeichnung wird aus dem Betreff extrahiert."""
    stelle = _extract_bewerbung_stelle(_BEWERBUNG_TEXT)
    assert stelle  # nicht leer
    assert "Karosserie" in stelle or "Fahrzeug" in stelle


def test_bewerbung_subject_enthaelt_stelle():
    """_extract_subject gibt 'Bewerbung-<Stelle>' zurück."""
    result = _extract_subject(_BEWERBUNG_TEXT)
    assert result.startswith("Bewerbung-")
    assert "Karosserie" in result or "Fahrzeug" in result


def test_bewerbung_full_pipeline():
    """Vollständige Pipeline liefert sinnvollen Dateinamen."""
    result = _via_rules(_BEWERBUNG_TEXT, "20260414001.pdf")
    assert "2026-04-14" in result
    # Absender ist Bewerber-Name, nicht Fließtext
    assert "selbstverstaendlich" not in result.lower()
    assert "gleichzeitig" not in result.lower()
    # Dokumenttyp enthält Bewerbung
    assert "Bewerbung" in result


def test_bewerbung_kein_uber_ocr_artefakt():
    """OCR 'Uber' (aus 'Über') darf nicht als Uber-Brand matchen wenn Bewerbung."""
    # "Uber" ist OCR-Artefakt für "Über" in "Über eine Einladung..."
    text = (
        "Uber eine Einladung zu einem Vorstellungsgesprach freue ich mich sehr.\n"
        "Ich bewerbe mich hiermit um die ausgeschriebene Stelle.\n"
        "\nBewerbung als Entwickler\n"
        "\nMit freundlichen Grüßen\n\nKlaus Mustermann\n"
    )
    sender = _extract_sender(text)
    # Darf nicht die ganze Fließtextzeile zurückgeben
    assert "Einladung" not in sender
    assert "freue" not in sender.lower()


def test_kein_ladung_falschtreffer():
    """'Ladung' darf nicht durch 'Einladung' im Text getriggert werden."""
    text = "Über eine Einladung zu einem Vorstellungsgespräch freue ich mich."
    result = _extract_subject(text)
    assert result != "Ladung"


def test_kein_klage_in_erklaerung():
    """'klage' darf nicht in 'Erklärung' matchen."""
    text = "Datenschutzerklärung der Muster GmbH"
    result = _extract_subject(text)
    assert result != "Klage"


def test_subject_kuendigung_als_ganzes_wort():
    """'Kündigung' als eigenständiges Wort wird korrekt erkannt."""
    text = "Kündigung des Mobilfunkvertrages"
    assert _extract_subject(text) == "Kuendigung"



# ------------------------------------- Regressionen: Absender-Falschtreffer

def test_sender_not_taken_from_body_with_common_words():
    """Alltagswörter wie "Netto", "das", "UPS" sind keine Firmennamen."""
    cases = {
        "Müller Haustechnik\nHauptstr. 5\n79100 Freiburg\nRechnung Nr. 2026-117\nSumme Netto 100,00 EUR":
            "Mueller-Haustechnik",
        "Schreinerei Huber\nSehr geehrter Herr Muster,\nanbei erhalten Sie das Angebot für Ihre Küche.":
            "Schreinerei-Huber",
        "Elektro Schmid\nLieferschein 4711\nVersand via UPS":
            "Elektro-Schmid",
    }
    for text, expected in cases.items():
        assert _extract_sender(text) == expected


def test_sender_brand_in_body_line_returns_short_name():
    """Steht die Marke mitten in einem Satz, nicht die ganze Zeile übernehmen."""
    text = "Ihr Vertrag\nwir danken Ihnen für Ihr Vertrauen in die Allianz und melden uns."
    assert _extract_sender(text) == "Allianz"


def test_sender_specific_entry_beats_generic():
    """Früher gewann "aok" vor "aok nordwest" allein durch die Dict-Reihenfolge."""
    text = "AOK NordWest · Postfach 1 · 44000 Dortmund\nIhr Beitragsbescheid"
    assert _extract_sender(text) == "AOK-NordWest"


def test_sender_word_boundaries():
    """Teilwörter treffen nicht: "Telekommunikation" ist nicht Telekom,
    "27 Zoll" ist keine Zollbehörde."""
    assert _extract_sender("Meier IT\nTelekommunikationsanlage Wartung") != "Telekom"
    assert _extract_sender("Monitor Shop\nBildschirm 27 Zoll") != "Zoll"


def test_company_suffix_needs_whole_word():
    """" eg" darf nicht in " egal" treffen."""
    text = "Das ist egal und so weiter\nKunde 4711"
    assert _extract_sender(text) != "Das-ist-egal-und-so-weiter"


def test_branchen_keys_unique_and_lowercase():
    """Doppelte Schlüssel überschreiben sich stillschweigend – per AST prüfen."""
    tree = ast.parse(Path(__file__).parent.parent.joinpath("src", "renamer.py").read_text("utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict) \
                and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id in ("MONATE", "BEKANNTE_BEHOERDEN", "DOKUMENTTYPEN", "BEKANNTE_BRANCHEN"):
            keys = [k.value for k in node.value.keys]
            dupes = [k for k, c in collections.Counter(keys).items() if c > 1]
            assert not dupes, f"{node.targets[0].id}: doppelte Schlüssel {dupes}"
            assert all(k == k.lower() for k in keys), node.targets[0].id
    for word in ("netto", "das", "real", "ups", "otto", "sky", "wise", "ergo", "uber", "zoll"):
        assert word not in BEKANNTE_BRANCHEN


def test_date_block_only_same_line():
    """Ein "fällig" in der Vorzeile darf das Briefdatum nicht sperren."""
    text = "Betrag fällig\n12.03.2026"
    assert _extract_date(text, "x.pdf") == "2026-03-12"
    assert _extract_date("geb. 01.02.1980\nFreiburg, 05.06.2026", "x.pdf") == "2026-06-05"


def test_mahnstufe_recognized():
    assert _extract_subject("Ihre Kundennummer 1\n2. Mahnung\nBitte zahlen Sie") == "2-Mahnung"


# ------------------------------------------------------ Template-Erweiterungen

def test_apply_template_subfolders():
    result = apply_template("{JAHR}/{MONAT}/{DATUM}_{ABSENDER}", "2026-05-08", "Allianz", "Police")
    assert result == "2026/05/2026-05-08_Allianz"


def test_apply_template_english_tokens():
    result = apply_template("{DATE}_{SENDER}_{SUBJECT}", "2026-05-08", "Apple", "Invoice")
    assert result == "2026-05-08_Apple_Invoice"


def test_apply_template_never_empty():
    assert apply_template("{UNBEKANNT}", "2026-05-08", "", "", original_stem="20260508001") == "20260508001"
    assert apply_template("", "2026-05-08", "", "") == "Dokument"


def test_apply_template_no_traversal_or_reserved_names():
    result = apply_template("../{ABSENDER}/CON", "2026-05-08", "X", "Y")
    assert ".." not in result.split("/")
    assert result.split("/")[-1].lower() != "con"
