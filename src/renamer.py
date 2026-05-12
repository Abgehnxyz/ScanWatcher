"""
@file    renamer.py
@project Scan Watcher
@company Nova Network
@date    Mai 2026
@brief   Dateinamen-Bestimmung aus extrahiertem OCR-Text.
         Stufe 1: Claude API (optional, erfordert API-Key).
         Stufe 2: Regelbasierte Extraktion – Datum, Absender, Betreff (offline).
"""

import logging
import re
from datetime import datetime
from pathlib import Path

log = logging.getLogger("scan_watcher.renamer")

MONATE = {
    "jan": 1, "feb": 2, "mar": 3, "maer": 3, "apr": 4,
    "mai": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "okt": 10, "nov": 11, "dez": 12,
}

# Nur Behörden/öffentliche Stellen – private Firmennamen gehören in die
# Absender-Whitelist in den Einstellungen, nicht in den Source-Code.
BEKANNTE_BEHOERDEN = {
    # Gerichte
    "bundesgerichtshof": "BGH",
    "bundesverfassungsgericht": "BVerfG",
    "bundesverwaltungsgericht": "BVerwG",
    "oberlandesgericht": "OLG",
    "landgericht": "Landgericht",
    "amtsgericht": "Amtsgericht",
    "arbeitsgericht": "Arbeitsgericht",
    "sozialgericht": "Sozialgericht",
    "verwaltungsgericht": "Verwaltungsgericht",
    "finanzgericht": "Finanzgericht",
    "staatsanwaltschaft": "Staatsanwaltschaft",
    "gerichtsvollzieher": "Gerichtsvollzieher",
    # Steuern & Zoll
    "finanzamt": "Finanzamt",
    "bundeszentralamt für steuern": "BZSt",
    "bundeszentralamt fuer steuern": "BZSt",
    "bzst": "BZSt",
    "hauptzollamt": "Hauptzollamt",
    "zollamt": "Zollamt",
    "zoll": "Zoll",
    # Renten & Soziales
    "deutsche rentenversicherung bund": "DRV-Bund",
    "deutsche rentenversicherung": "DRV",
    "drv bund": "DRV-Bund",
    "drv": "DRV",
    "versorgungsamt": "Versorgungsamt",
    "sozialamt": "Sozialamt",
    "jugendamt": "Jugendamt",
    "gesundheitsamt": "Gesundheitsamt",
    "bafög-amt": "BAFoeG-Amt",
    "bafoeg": "BAFoeG-Amt",
    "studentenwerk": "Studentenwerk",
    # Arbeit
    "bundesagentur fuer arbeit": "Bundesagentur-Arbeit",
    "bundesagentur für arbeit": "Bundesagentur-Arbeit",
    "agentur für arbeit": "Agentur-Arbeit",
    "agentur fuer arbeit": "Agentur-Arbeit",
    "jobcenter": "Jobcenter",
    "berufsgenossenschaft": "BG",
    "unfallkasse": "Unfallkasse",
    # Regulierung & Aufsicht
    "bundesanstalt für finanzdienstleistungsaufsicht": "BaFin",
    "bafin": "BaFin",
    "bundesnetzagentur": "Bundesnetzagentur",
    "kraftfahrt-bundesamt": "KBA",
    "kraftfahrtbundesamt": "KBA",
    "kba": "KBA",
    "bundesamt für": "Bundesamt",
    # Rundfunk
    "beitragsservice von ard": "Beitragsservice",
    "ard zdf deutschlandradio beitragsservice": "Beitragsservice",
    "beitragsservice": "Beitragsservice",
    "rundfunkbeitrag": "Beitragsservice",
    # Melde- & Verwaltung
    "einwohnermeldeamt": "Einwohnermeldeamt",
    "kfz-zulassungsstelle": "KFZ-Zulassung",
    "kfz zulassungsstelle": "KFZ-Zulassung",
    "zulassungsstelle": "KFZ-Zulassung",
    "gewerbeamt": "Gewerbeamt",
    "ordnungsamt": "Ordnungsamt",
    "bauamt": "Bauamt",
    "standesamt": "Standesamt",
    "stadtverwaltung": "Stadtverwaltung",
    "kreisverwaltung": "Kreisverwaltung",
    "gemeindeverwaltung": "Gemeindeverwaltung",
    "landratsamt": "Landratsamt",
    "bezirksamt": "Bezirksamt",
    "kämmerei": "Kaemmerei",
    "kaemmerei": "Kaemmerei",
    "stadtwerke": "Stadtwerke",
    # Polizei & Sicherheit
    "polizeipräsidium": "Polizei",
    "polizeipraesidium": "Polizei",
    "polizeidirektion": "Polizei",
    "landeskriminalamt": "LKA",
    "bundeskriminalamt": "BKA",
}

# Unternehmens-Suffixe für heuristische Absendererkennung
_COMPANY_SUFFIXES = [
    " gmbh", " ag", " kg", " ohg", " gbr", " ug", " e.v.", " ev",
    " gmbh & co", " co. kg", " mbh",
    " eg", " e.g.",           # Genossenschaften (Volksbank, Raiffeisenbank …)
    " kag", " stiftung",
]

# Regex für Adress- und Empfängerzeilen – werden im Fallback übersprungen
_RE_ADDRESS = re.compile(
    r"\b\d{5}\b"                               # PLZ
    r"|str\.\s|straße\b|strasse\b"             # Straßentypen
    r"|\bweg\b|\bplatz\b|\bgasse\b|\ballee\b"
    r"|\bpostfach\b"
    r"|\btel\.?\b|\bfax\.?\b|\bwww\.\b|\b@\b"  # Kontaktdaten
    r"|\bsepa\b|\biban\b|\bbic\b",              # Bankdaten-Zeilen
    re.IGNORECASE,
)

DOKUMENTTYPEN = {
    # ── Rechnungen & Zahlungen ───────────────────────────────────────────────
    "mahnung": "Mahnung", "zahlungserinnerung": "Zahlungserinnerung",
    "2. mahnung": "2-Mahnung", "3. mahnung": "3-Mahnung",
    "erinnerung": "Erinnerung", "rechnung": "Rechnung",
    "beitragsrechnung": "Beitragsrechnung", "abrechnung": "Abrechnung",
    "jahresabrechnung": "Jahresabrechnung", "kontoauszug": "Kontoauszug",
    "quittung": "Quittung", "kostenrechnung": "Kostenrechnung",
    "kassenbon": "Kassenbon", "kassenbeleg": "Kassenbeleg",
    "proforma-rechnung": "Proforma-Rechnung",
    "gutschrift": "Gutschrift", "stornierung": "Stornierung",
    "lastschrift": "Lastschriftmandat", "sepa-mandat": "SEPA-Mandat",
    "einzugsermächtigung": "Einzugsermaechtigung",
    # ── Konten & Depot ───────────────────────────────────────────────────────
    "kontoabschluss": "Kontoabschluss",
    "depotauszug": "Depotauszug",
    "depotabrechnung": "Depotabrechnung",
    "wertpapierabrechnung": "Wertpapierabrechnung",
    "jahressteuerbescheinigung": "Jahressteuerbescheinigung",
    "steuerbescheinigung": "Steuerbescheinigung",
    "freistellungsauftrag": "Freistellungsauftrag",
    "freistellungsbescheinigung": "Freistellungsbescheinigung",
    "kontoeröffnung": "Kontoeröffnung",
    "kontoschließung": "Kontoschliesssung",
    "girokonto": "Girokonto",
    # ── Behördliche Dokumente ────────────────────────────────────────────────
    "bescheid": "Bescheid", "steuerbescheid": "Steuerbescheid",
    "grundsteuerbescheid": "Grundsteuerbescheid",
    "gewerbesteuerbescheid": "Gewerbesteuerbescheid",
    "einkommensteuerbescheid": "ESt-Bescheid",
    "umsatzsteuerbescheid": "USt-Bescheid",
    "feststellungsbescheid": "Feststellungsbescheid",
    "bewilligungsbescheid": "Bewilligungsbescheid",
    "ablehnungsbescheid": "Ablehnungsbescheid",
    "bescheinigung": "Bescheinigung",
    "bestätigung": "Bestaetigung", "bestaetigung": "Bestaetigung",
    "meldebescheinigung": "Meldebescheinigung",
    "lohnsteuerbescheinigung": "Lohnsteuerbescheinigung",
    "einkommensteuererklärung": "ESt-Erklaerung",
    "steuererklärung": "Steuererklarung",
    "umsatzsteuervoranmeldung": "USt-Voranmeldung",
    "gewerbeanmeldung": "Gewerbeanmeldung",
    "gewerbeabmeldung": "Gewerbeabmeldung",
    "handelsregisterauszug": "Handelsregisterauszug",
    "grundbuchauszug": "Grundbuchauszug",
    # ── Verträge & Rechtliches ───────────────────────────────────────────────
    "kündigung": "Kuendigung", "kuendigung": "Kuendigung",
    "vertrag": "Vertrag", "nachtrag": "Vertragsnachtrag",
    "rahmenvertrag": "Rahmenvertrag",
    "kaufvertrag": "Kaufvertrag",
    "mietvertrag": "Mietvertrag",
    "pachtvertrag": "Pachtvertrag",
    "arbeitsvertrag": "Arbeitsvertrag",
    "dienstleistungsvertrag": "Dienstleistungsvertrag",
    "vollmacht": "Vollmacht", "vollmachtsurkunde": "Vollmacht",
    "urteil": "Urteil", "beschluss": "Beschluss",
    "gutachten": "Gutachten", "ladung": "Ladung",
    "zustellungsurkunde": "Zustellungsurkunde",
    "guetetermin": "Guetetermin", "haupttermin": "Haupttermin",
    "mahnbescheid": "Mahnbescheid",
    "vollstreckungsbescheid": "Vollstreckungsbescheid",
    "pfändung": "Pfaendung", "pfaendung": "Pfaendung",
    "datenschutzerklärung": "Datenschutzerklaerung",
    "einwilligungserklärung": "Einwilligungserklaerung",
    # ── Wohnen & Immobilien ──────────────────────────────────────────────────
    "nebenkostenabrechnung": "Nebenkostenabrechnung",
    "betriebskostenabrechnung": "Betriebskostenabrechnung",
    "heizkostenabrechnung": "Heizkostenabrechnung",
    "mieterhöhung": "Mieterhoehung",
    "mieterhoehung": "Mieterhoehung",
    "wohnungsübergabe": "Wohnungsuebergabe",
    "übergabeprotokoll": "Uebergabeprotokoll",
    "kautionsrückzahlung": "Kautionsrueckzahlung",
    "grundsteuer": "Grundsteuer",
    "hausgeld": "Hausgeld",
    "wohngeld": "Wohngeld",
    "eigentümerversammlung": "Eigentuemversammlung",
    "teilungserklärung": "Teilungserklaerung",
    # ── Gehalt & Arbeit ──────────────────────────────────────────────────────
    "gehaltsabrechnung": "Gehaltsabrechnung",
    "lohnabrechnung": "Lohnabrechnung",
    "entgeltabrechnung": "Entgeltabrechnung",
    "abmahnung": "Abmahnung",
    "aufhebungsvertrag": "Aufhebungsvertrag",
    "arbeitnehmerüberlassung": "Arbeitnehmerueberlassung",
    "sozialversicherungsausweis": "SV-Ausweis",
    "versicherungsnummer": "Versicherungsnummer",
    # ── Gesundheit & Medizin ─────────────────────────────────────────────────
    "arztbrief": "Arztbrief",
    "befund": "Befund",
    "laborbefund": "Laborbefund",
    "röntgenbefund": "Roentgenbefund",
    "überweisung": "Ueberweisung",
    "rezept": "Rezept",
    "krankschreibung": "Krankschreibung",
    "arbeitsunfähigkeitsbescheinigung": "AU-Bescheinigung",
    "au-bescheinigung": "AU-Bescheinigung",
    "entlassungsbrief": "Entlassungsbrief",
    "arztrechnung": "Arztrechnung",
    "heil- und kostenplan": "Heil-Kostenplan",
    "kostenvoranschlag": "Kostenvoranschlag",
    "patientenverfügung": "Patientenverfuegung",
    "vorsorgevollmacht": "Vorsorgevollmacht",
    "pflegegutachten": "Pflegegutachten",
    # ── Versicherung ─────────────────────────────────────────────────────────
    "police": "Versicherungspolice",
    "versicherungsschein": "Versicherungsschein",
    "schadenmeldung": "Schadenmeldung",
    "schadenregulierung": "Schadenregulierung",
    "schadensanzeige": "Schadensanzeige",
    "beitragsanpassung": "Beitragsanpassung",
    "versicherungsnachweis": "Versicherungsnachweis",
    # ── Mitteilungen & Korrespondenz ─────────────────────────────────────────
    "servicemitteilung": "Servicemitteilung",
    "mitteilung": "Mitteilung", "information": "Information",
    "hinweis": "Hinweis", "ankündigung": "Ankuendigung",
    "ankuendigung": "Ankuendigung", "anschreiben": "Anschreiben",
    "angebot": "Angebot", "auftragsbestätigung": "Auftragsbestaetigung",
    "auftragsbestaetigung": "Auftragsbestaetigung",
    "lieferschein": "Lieferschein",
    "lieferbestätigung": "Lieferbestaetigung",
    "versandbestätigung": "Versandbestaetigung",
    "rücksendung": "Ruecksendung",
    "reklamation": "Reklamation",
    # ── KFZ ──────────────────────────────────────────────────────────────────
    "zulassungsbescheinigung": "Zulassungsbescheinigung",
    "fahrzeugschein": "Fahrzeugschein",
    "fahrzeugbrief": "Fahrzeugbrief",
    "hauptuntersuchung": "HU",
    "hu-bericht": "HU-Bericht",
    "hauptuntersuchungsbericht": "HU-Bericht",
    "kraftfahrzeugsteuer": "Kfz-Steuer",
    "kfz-steuer": "Kfz-Steuer",
    "bußgeldbescheid": "Bussgeld",
    "bussgeld": "Bussgeld",
    # ── Sonstiges ────────────────────────────────────────────────────────────
    "antrag": "Antrag", "widerspruch": "Widerspruch",
    "einspruch": "Einspruch", "klage": "Klage",
    "protokoll": "Protokoll", "zeugnis": "Zeugnis",
    "urkunde": "Urkunde",
    "spendenbescheinigung": "Spendenbescheinigung",
    "spendenquittung": "Spendenbescheinigung",
    "mitgliedsbescheinigung": "Mitgliedsbescheinigung",
    "mitgliedsausweis": "Mitgliedsausweis",
    # ── Bewerbung ────────────────────────────────────────────────────────────
    "bewerbung": "Bewerbung", "motivationsschreiben": "Motivationsschreiben",
    "lebenslauf": "Lebenslauf", "curriculum vitae": "Lebenslauf",
    "arbeitszeugnis": "Arbeitszeugnis", "zwischenzeugnis": "Zwischenzeugnis",
    "bewerbungsunterlagen": "Bewerbungsunterlagen",
}


def clean(text: str, space_replacement: str = "-") -> str:
    """Sonderzeichen fuer Dateinamen normalisieren."""
    replacements = {
        "ae": ["ä"], "oe": ["ö"], "ue": ["ü"],
        "Ae": ["Ä"], "Oe": ["Ö"], "Ue": ["Ü"],
        "ss": ["ß"],
        space_replacement: [" ", "/", "\\"],
        "": [":", ";", ",", '"', "'", "(", ")", "[", "]", "!", "?"],
        "u": ["&"],
    }
    for new, olds in replacements.items():
        for old in olds:
            text = text.replace(old, new)
    text = re.sub(r"[^A-Za-z0-9\-_]", "", text)
    text = re.sub(r"-{2,}", "-", text)
    text = re.sub(r"_{2,}", "_", text)
    return text.strip("-_")


def _format_date(datum_raw: str, date_format: str) -> str:
    """Konvertiert YYYY-MM-DD (oder YYYY-MM) in das gewuenschte Ausgabeformat."""
    try:
        if len(datum_raw) >= 10:
            dt = datetime.strptime(datum_raw[:10], "%Y-%m-%d")
        else:
            dt = datetime.strptime(datum_raw, "%Y-%m")
        if date_format == "DD.MM.YYYY":
            return dt.strftime("%d.%m.%Y")
        if date_format == "YYYYMMDD":
            return dt.strftime("%Y%m%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return datum_raw


def apply_template(
    template: str,
    datum_raw: str,
    absender: str,
    betreff: str,
    original_stem: str = "",
    date_format: str = "YYYY-MM-DD",
    space_replacement: str = "-",
) -> str:
    """Wendet das Benennungsschema-Template auf die extrahierten Werte an."""
    datum_fmt = _format_date(datum_raw, date_format)
    try:
        parse_str = datum_raw[:10] if len(datum_raw) >= 10 else (datum_raw + "-01")
        dt = datetime.strptime(parse_str[:10], "%Y-%m-%d")
        jahr, monat, tag = dt.strftime("%Y"), dt.strftime("%m"), dt.strftime("%d")
    except ValueError:
        jahr = datum_raw[:4] if len(datum_raw) >= 4 else "0000"
        monat = datum_raw[5:7] if len(datum_raw) >= 7 else "01"
        tag = datum_raw[8:10] if len(datum_raw) >= 10 else "01"

    result = template
    result = result.replace("{DATUM}", datum_fmt)
    result = result.replace("{JAHR}", jahr)
    result = result.replace("{MONAT}", monat)
    result = result.replace("{TAG}", tag)
    result = result.replace("{ABSENDER}", clean(absender, space_replacement))
    result = result.replace("{BETREFF}", clean(betreff, space_replacement))
    result = result.replace("{ORIGINAL}", clean(original_stem, space_replacement))
    result = result.replace("{ZAEHLER}", "")
    result = re.sub(r"\{[^}]{1,20}\}", "", result)   # unbekannte Tokens entfernen
    result = re.sub(r'[\\/:*?"<>|\x00]', "", result)  # Windows-unvertraegliche Zeichen
    result = re.sub(r"-{2,}", "-", result)
    result = re.sub(r"_{2,}", "_", result)
    return result.strip("-_. ")[:120]


def determine_name(
    text: str,
    original_filename: str,
    active_model: str = "rules",
    model_keys: dict | None = None,
    ollama_model: str = "llama3.2",
    name_template: str = "{DATUM}_{ABSENDER}_{BETREFF}",
    date_format: str = "YYYY-MM-DD",
    space_replacement: str = "-",
    custom_senders: dict | None = None,
    custom_doc_types: dict | None = None,
) -> str:
    """Dateinamen bestimmen – aktives KI-Modell, Fallback: Regelwerk."""
    keys = model_keys or {}
    name = None
    try:
        if active_model == "claude" and keys.get("claude"):
            name = _via_claude(text, original_filename, keys["claude"], name_template, date_format, space_replacement)
        elif active_model == "openai" and keys.get("openai"):
            name = _via_openai_compat(
                text, original_filename, keys["openai"],
                "https://api.openai.com/v1", "gpt-4o-mini",
                name_template, date_format, space_replacement, "OpenAI",
            )
        elif active_model == "gemini" and keys.get("gemini"):
            name = _via_gemini(text, original_filename, keys["gemini"], name_template, date_format, space_replacement)
        elif active_model == "mistral" and keys.get("mistral"):
            name = _via_openai_compat(
                text, original_filename, keys["mistral"],
                "https://api.mistral.ai/v1", "mistral-small-latest",
                name_template, date_format, space_replacement, "Mistral",
            )
        elif active_model == "groq" and keys.get("groq"):
            name = _via_openai_compat(
                text, original_filename, keys["groq"],
                "https://api.groq.com/openai/v1", "llama-3.1-8b-instant",
                name_template, date_format, space_replacement, "Groq",
            )
        elif active_model == "ollama":
            name = _via_ollama(text, original_filename, ollama_model, name_template, date_format, space_replacement)
    except Exception as e:
        log.warning(f"{active_model}: {e}")
    if name:
        return name
    return _via_rules(text, original_filename, name_template, date_format, space_replacement, custom_senders, custom_doc_types)


def _build_prompt_header(name_template: str, date_format: str, space_replacement: str) -> str:
    """Gemeinsamer Prompt-Header fuer Claude und Ollama."""
    example = apply_template(
        name_template, "2026-04-01", "inView", "Rechnung RE10154",
        date_format=date_format, space_replacement=space_replacement,
    )
    return (
        f"Format-Template: {name_template}\n"
        f"Datumsformat: {date_format}\n"
        f"Leerzeichen ersetzen durch: \"{space_replacement}\"\n"
        f"Regeln: Umlaute ersetzen (ae/oe/ue/ss), max 120 Zeichen.\n"
        f"Nur den Dateinamen zurueckgeben (ohne .pdf), kein Erklaerungstext.\n\n"
        f"Beispiel-Output: {example}\n"
    )


def _via_openai_compat(
    text: str,
    original_filename: str,
    api_key: str,
    base_url: str,
    model_id: str,
    name_template: str,
    date_format: str,
    space_replacement: str,
    provider_name: str,
) -> str | None:
    """OpenAI-kompatibler Endpunkt (OpenAI, Mistral, Groq)."""
    import json
    import urllib.request

    prompt = (
        "Bestimme fuer dieses gescannte Dokument den Dateinamen.\n"
        + _build_prompt_header(name_template, date_format, space_replacement)
        + f"\nOCR-Text:\n{text[:3000]}"
    )
    payload = json.dumps({
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 200,
        "temperature": 0,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        name = data["choices"][0]["message"]["content"].strip().replace(".pdf", "")
        log.info(f"  Benennung: {provider_name}")
        return name or None
    except Exception as e:
        log.warning(f"{provider_name}: {e}")
        return None


def _via_gemini(
    text: str,
    original_filename: str,
    api_key: str,
    name_template: str,
    date_format: str,
    space_replacement: str,
) -> str | None:
    """Dateinamen per Google Gemini API bestimmen."""
    import json
    import urllib.request

    prompt = (
        "Bestimme fuer dieses gescannte Dokument den Dateinamen.\n"
        + _build_prompt_header(name_template, date_format, space_replacement)
        + f"\nOCR-Text:\n{text[:3000]}"
    )
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models"
        f"/gemini-1.5-flash:generateContent?key={api_key}"
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 200, "temperature": 0},
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        name = data["candidates"][0]["content"]["parts"][0]["text"].strip().replace(".pdf", "")
        log.info("  Benennung: Gemini")
        return name or None
    except Exception as e:
        log.warning(f"Gemini: {e}")
        return None


def _via_claude(
    text: str,
    original_filename: str,
    api_key: str,
    name_template: str = "{DATUM}_{ABSENDER}_{BETREFF}",
    date_format: str = "YYYY-MM-DD",
    space_replacement: str = "-",
) -> str | None:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key, timeout=30.0)
        prompt = (
            "Bestimme fuer dieses gescannte Dokument den Dateinamen.\n"
            + _build_prompt_header(name_template, date_format, space_replacement)
            + f"\nOCR-Text:\n{text[:3000]}"
        )
        resp = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        name = resp.content[0].text.strip().replace(".pdf", "")
        log.info("  Benennung: Claude API")
        return name or None
    except Exception as e:
        log.warning(f"Claude API: {e}")
        return None


def _via_ollama(
    text: str,
    original_filename: str,
    model: str,
    name_template: str = "{DATUM}_{ABSENDER}_{BETREFF}",
    date_format: str = "YYYY-MM-DD",
    space_replacement: str = "-",
) -> str | None:
    """Dateinamen per lokalem Ollama-Modell bestimmen (kein Internet noetig)."""
    import json
    import urllib.request

    prompt = (
        "Bestimme fuer dieses gescannte Dokument den Dateinamen.\n"
        + _build_prompt_header(name_template, date_format, space_replacement)
        + f"\nOCR-Text:\n{text[:3000]}"
    )
    try:
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        name = data.get("response", "").strip().replace(".pdf", "").strip('\'"')
        if name:
            log.info(f"  Benennung: Ollama ({model})")
            return name
        return None
    except Exception as e:
        log.warning(f"Ollama: {e}")
        return None


def _via_rules(
    text: str,
    original_filename: str,
    name_template: str = "{DATUM}_{ABSENDER}_{BETREFF}",
    date_format: str = "YYYY-MM-DD",
    space_replacement: str = "-",
    custom_senders: dict | None = None,
    custom_doc_types: dict | None = None,
) -> str:
    datum_raw = _extract_date(text, original_filename)
    absender = _extract_sender(text, space_replacement, custom_senders)
    betreff = _extract_subject(text, space_replacement, custom_doc_types)
    log.info("  Benennung: Lokale Regeln")
    return apply_template(
        name_template, datum_raw, absender, betreff,
        Path(original_filename).stem, date_format, space_replacement,
    )


def _extract_date(text: str, original_filename: str) -> str:
    # DD.MM.YYYY
    m = re.search(r"\b(\d{1,2})\.(\d{2})\.(\d{4})\b", text)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"

    # DD. Monatsname YYYY
    m = re.search(
        r"\b(\d{1,2})\.\s*(Januar|Februar|März|Maerz|April|Mai|Juni|Juli|"
        r"August|September|Oktober|November|Dezember)\s+(\d{4})\b",
        text, re.IGNORECASE
    )
    if m:
        mo = MONATE.get(m.group(2)[:3].lower(), 0)
        if mo:
            return f"{m.group(3)}-{mo:02d}-{int(m.group(1)):02d}"

    # Datum aus Originaldateiname (Format YYYYMMDDxxxx)
    stem = Path(original_filename).stem
    if len(stem) >= 8 and stem[:8].isdigit():
        return f"{stem[:4]}-{stem[4:6]}-{stem[6:8]}"

    return datetime.now().strftime("%Y-%m")


# Bekannte Institutionen/Marken – allgemeingültig, kein Personenbezug.
# Gesucht in den ersten 30 Zeilen (deckt Briefkopf UND Unterschriftsblock ab).
# Länge sortiert: längere/spezifischere Einträge werden zuerst geprüft,
# damit "kreissparkasse" vor "sparkasse" trifft.
BEKANNTE_BRANCHEN = {
    # ── Genossenschaftsbanken ────────────────────────────────────────────────
    "raiffeisenbank": "Raiffeisenbank",
    "volksbank": "Volksbank",
    "vr-bank": "VR-Bank",
    "vr bank": "VR-Bank",
    "psd bank": "PSD-Bank",
    "sparda-bank": "Sparda-Bank",
    "sparda bank": "Sparda-Bank",
    "berliner volksbank": "Berliner-Volksbank",
    "apobank": "ApoBank",
    "deutsche apotheker": "ApoBank",
    "liga bank": "Liga-Bank",
    "teambank": "TeamBank",
    "easybank": "EasyBank",

    # ── Sparkassen ───────────────────────────────────────────────────────────
    "kreissparkasse": "Kreissparkasse",
    "stadtsparkasse": "Stadtsparkasse",
    "nassauische sparkasse": "Nassauische-Sparkasse",
    "hamburger sparkasse": "Haspa",
    "haspa": "Haspa",
    "sparkasse": "Sparkasse",
    "landesbank": "Landesbank",
    "helaba": "Helaba",
    "lbbw": "LBBW",
    "Bayern lb": "BayernLB",
    "bayernlb": "BayernLB",
    "nord/lb": "NordLB",
    "nordlb": "NordLB",
    "deka bank": "DekaBank",
    "dekabank": "DekaBank",
    "s-broker": "S-Broker",

    # ── Große Privatbanken ───────────────────────────────────────────────────
    "hypovereinsbank": "HypoVereinsbank",
    "commerzbank": "Commerzbank",
    "deutsche bank": "Deutsche-Bank",
    "postbank": "Postbank",
    "targobank": "Targobank",
    "comdirect": "Comdirect",
    "ing-diba": "ING",
    "ing direkt": "ING",
    "ing bank": "ING",
    "dkb deutsche kreditbank": "DKB",
    "dkb": "DKB",
    "norisbank": "Norisbank",
    "santander": "Santander",
    "unicredit": "UniCredit",
    "bnp paribas": "BNP-Paribas",
    "deutsche pfandbriefbank": "pbb",
    "oddo bhf": "Oddo-BHF",
    "berenberg": "Berenberg",
    "hsbc": "HSBC",
    "citibank": "Citibank",
    "american express": "AmericanExpress",
    "barclays": "Barclays",

    # ── Bausparkassen ────────────────────────────────────────────────────────
    "schwäbisch hall": "Schwaebisch-Hall",
    "schwaebisch hall": "Schwaebisch-Hall",
    "wüstenrot": "Wuestenrot",
    "wuestenrot": "Wuestenrot",
    "lbs bausparkasse": "LBS",
    "lbs": "LBS",
    "bauspar": "Bausparkasse",
    "bmw bank": "BMW-Bank",
    "mercedes-benz bank": "Mercedes-Benz-Bank",
    "volkswagen bank": "VW-Bank",
    "vw bank": "VW-Bank",
    "porsche bank": "Porsche-Bank",
    "ford bank": "Ford-Bank",
    "opel bank": "Opel-Bank",
    "renault bank": "Renault-Bank",
    "toyota bank": "Toyota-Bank",

    # ── Versicherungen ───────────────────────────────────────────────────────
    "huk-coburg": "HUK-Coburg",
    "huk coburg": "HUK-Coburg",
    "allianz versicherung": "Allianz",
    "allianz se": "Allianz",
    "allianz": "Allianz",
    "r+v versicherung": "R+V",
    "r+v": "R+V",
    "signal iduna": "Signal-Iduna",
    "generali versicherung": "Generali",
    "generali": "Generali",
    "gothaer versicherung": "Gothaer",
    "gothaer": "Gothaer",
    "lvm versicherung": "LVM",
    "lvm": "LVM",
    "debeka": "Debeka",
    "barmenia": "Barmenia",
    "axa versicherung": "AXA",
    "axa": "AXA",
    "ergo versicherung": "Ergo",
    "ergo": "Ergo",
    "zurich versicherung": "Zurich",
    "zurich insurance": "Zurich",
    "zurich": "Zurich",
    "württembergische": "Wuerttembergische",
    "wuerttembergische": "Wuerttembergische",
    "bayerische beamtenkrankenkasse": "BBKK",
    "münchener verein": "Muenchener-Verein",
    "münchener rückversicherung": "MunichRe",
    "münchener rück": "MunichRe",
    "hannover rück": "HannoverRe",
    "hannover re": "HannoverRe",
    "continentale": "Continentale",
    "provinzial": "Provinzial",
    "sparkassen versicherung": "SV-Versicherung",
    "sv sparkassen": "SV-Versicherung",
    "inter versicherung": "Inter-Versicherung",
    "inter rückversicherung": "Inter-Versicherung",
    "itzehoer": "Itzehoer",
    "concordia": "Concordia",
    "nürnberger versicherung": "Nuernberger",
    "nürnberger": "Nuernberger",
    "nuernberger": "Nuernberger",
    "alte leipziger": "Alte-Leipziger",
    "hallesche": "Hallesche",
    "deurag": "DEURAG",
    "devk versicherung": "DEVK",
    "devk": "DEVK",
    "vhv versicherung": "VHV",
    "vhv": "VHV",
    "ba die bayerische": "Die-Bayerische",
    "die bayerische": "Die-Bayerische",
    "bayerische": "Die-Bayerische",
    "advocard": "Advocard",
    "roland rechtsschutz": "Roland-Rechtsschutz",
    "roland rechtsschutzversicherung": "Roland-Rechtsschutz",
    "arag": "ARAG",
    "das rechtsschutz": "DAS",
    "das": "DAS",
    "adac versicherung": "ADAC-Versicherung",
    "adac": "ADAC",
    "kravag": "KRAVAG",
    "sv gebäudeversicherung": "SV-Gebaeudeversicherung",
    "württembergische gebäude": "WGV",
    "wgv": "WGV",
    "amv": "AMV",
    "hdi versicherung": "HDI",
    "hdi": "HDI",
    "talanx": "Talanx",
    "baloise": "Baloise",
    "helvetia": "Helvetia",
    "swiss life": "Swiss-Life",
    "css versicherung": "CSS",
    "uniqa": "UNIQA",
    "österreichische versicherung": "Oesterreichische-Versicherung",
    "versicherungskammer": "Versicherungskammer",
    "maxpool": "Maxpool",

    # ── Krankenkassen ────────────────────────────────────────────────────────
    "techniker krankenkasse": "TK",
    "barmer gek": "Barmer",
    "barmer": "Barmer",
    "dak-gesundheit": "DAK",
    "dak gesundheit": "DAK",
    "aok plus": "AOK",
    "aok": "AOK",
    "ikk classic": "IKK-Classic",
    "ikk gesund plus": "IKK-Gesund-Plus",
    "ikk": "IKK",
    "knappschaft": "Knappschaft",
    "bkk mobil oil": "BKK-MobilOil",
    "bkk provita": "BKK-Provita",
    "bkk": "BKK",
    "pronova bkk": "PronovaBKK",
    "hkk": "HKK",
    "big direkt": "BIG-direkt",
    "viactiv": "Viactiv",
    "mhplus": "MHplus",
    "kkg gesundheitskasse": "KKG",
    "salus bkk": "Salus-BKK",
    "energie bkk": "Energie-BKK",
    "bertelsmann bkk": "Bertelsmann-BKK",
    "actimonda": "Actimonda",
    "bosch bkk": "Bosch-BKK",
    "siemens betriebskrankenkasse": "SBK",
    "sbk": "SBK",
    "bahn-bkk": "Bahn-BKK",
    "handelskrankenkasse": "HKK",
    "aok nordwest": "AOK-NordWest",
    "aok rheinland": "AOK-Rheinland",
    "aok bayern": "AOK-Bayern",
    "aok plus": "AOK-Plus",
    "aok niedersachsen": "AOK-Niedersachsen",
    "aok hessen": "AOK-Hessen",
    "aok sachsen-anhalt": "AOK-Sachsen-Anhalt",
    "aok bundesverband": "AOK",
    "aok": "AOK",
    "tkk": "TK",
    "techniker krankenkasse": "TK",
    "tk": "TK",
    "dak-gesundheit": "DAK",
    "dak gesundheit": "DAK",
    "dak": "DAK",
    "kk exklusiv": "KK-Exklusiv",
    "hek": "HEK",
    "bkk linde": "BKK-Linde",
    "bkk firmus": "BKK-Firmus",
    "bkk24": "BKK24",
    "bkk dürkopp adler": "BKK-Duerkopp-Adler",
    "mkk": "MKK",
    "securvita": "Securvita",
    "audi bkk": "Audi-BKK",
    "r+v bkk": "R+V-BKK",
    "mobil krankenkasse": "Mobil-Krankenkasse",
    "vdek": "vdek",

    # ── Telekommunikation – Festnetz & Mobilfunk ─────────────────────────────
    # Telekom
    "telekom deutschland gmbh": "Telekom",
    "telekom deutschland": "Telekom",
    "deutsche telekom ag": "Telekom",
    "deutsche telekom": "Telekom",
    "t-mobile": "Telekom",
    "t-systems": "T-Systems",
    "telekom": "Telekom",
    # Vodafone
    "vodafone gmbh": "Vodafone",
    "vodafone kabel deutschland": "Vodafone",
    "vodafone d2 gmbh": "Vodafone",
    "vodafone deutschland": "Vodafone",
    "vodafone": "Vodafone",
    "kabel deutschland": "Vodafone",
    # O2 / Telefónica
    "telefónica germany": "O2",
    "telefónica deutschland": "O2",
    "telefónica": "O2",
    "telefonica germany": "O2",
    "telefonica": "O2",
    "o2 telefónica": "O2",
    "o2 telefonica": "O2",
    "o2 germany": "O2",
    "o2": "O2",
    # 1&1
    "1&1 versatel": "1und1",
    "1&1 telekommunikation": "1und1",
    "1&1 drillisch": "1und1",
    "1&1": "1und1",
    "1und1": "1und1",
    "drillisch": "Drillisch",
    "windsim": "WinSim",
    # Congstar / Klarmobil / Aldi Talk etc.
    "congstar": "Congstar",
    "klarmobil": "Klarmobil",
    "aldi talk": "Aldi-Talk",
    "lidl connect": "Lidl-Connect",
    "simyo": "Simyo",
    "blau mobil": "Blau",
    "blau": "Blau",
    "smartmobil": "Smartmobil",
    "simply": "Simply",
    "otelo": "Otelo",
    "yourfone": "Yourfone",
    "netzclub": "Netzclub",
    "freenetmobile": "Freenet-Mobile",
    "freenet": "Freenet",
    "debitel": "Debitel",
    "eplus": "E-Plus",
    # Kabel-/DSL-Anbieter
    "unitymedia": "Unitymedia",
    "kabelbw": "KabelBW",
    "tele columbus": "Tele-Columbus",
    "pyur": "Pyur",
    "wilhelm.tel": "Wilhelm.tel",
    "ewe tel": "EWE-Tel",
    "netaachen": "NetAachen",
    "m-net": "M-net",
    "mnet": "M-net",
    "netcologne": "NetCologne",
    "lew telnet": "LEW-Telnet",
    "alice": "Alice",
    "arcor": "Arcor",
    "hansenet": "HanseNet",
    # Satellite / TV
    "sky deutschland": "Sky",
    "sky": "Sky",
    "disney+": "Disney-Plus",
    "disney plus": "Disney-Plus",
    "dazn": "DAZN",
    "amazon prime": "Amazon-Prime",
    "magenta tv": "MagentaTV",
    "magenta sport": "MagentaSport",

    # ── Internet & Hosting ───────────────────────────────────────────────────
    "ionos": "IONOS",
    "1&1 ionos": "IONOS",
    "strato ag": "Strato",
    "strato": "Strato",
    "hetzner online": "Hetzner",
    "hetzner": "Hetzner",
    "netcup": "Netcup",
    "domainfactory": "DomainFactory",
    "domain factory": "DomainFactory",
    "hosteurope": "HostEurope",
    "host europe": "HostEurope",
    "all-inkl": "All-Inkl",
    "webgo": "Webgo",
    "mittwald": "Mittwald",
    "contabo": "Contabo",
    "siteground": "Siteground",
    "godaddy": "GoDaddy",
    "cloudflare": "Cloudflare",
    "united internet": "United-Internet",

    # ── Online-Handel & Marktplätze ──────────────────────────────────────────
    "amazon payments europe": "Amazon",
    "amazon payments": "Amazon",
    "amazon.de": "Amazon",
    "amazon": "Amazon",
    "ebay gmbh": "eBay",
    "ebay": "eBay",
    "otto gmbh": "Otto",
    "otto": "Otto",
    "zalando se": "Zalando",
    "zalando": "Zalando",
    "mediamarkt": "MediaMarkt",
    "saturn": "Saturn",
    "ceconomy": "Ceconomy",
    "notebooksbilliger": "NBB",
    "nbb.com": "NBB",
    "cyberport": "Cyberport",
    "alternate": "Alternate",
    "pearl": "Pearl",
    "tchibo": "Tchibo",
    "bonprix": "Bonprix",
    "about you": "AboutYou",
    "shein": "SHEIN",
    "wish": "Wish",
    "temu": "Temu",
    "real.de": "Real",
    "kaufland": "Kaufland",

    # ── Software / Cloud / IT ────────────────────────────────────────────────
    "apple inc": "Apple",
    "apple": "Apple",
    "google llc": "Google",
    "google ireland": "Google",
    "google": "Google",
    "microsoft ireland": "Microsoft",
    "microsoft deutschland": "Microsoft",
    "microsoft": "Microsoft",
    "adobe systems": "Adobe",
    "adobe": "Adobe",
    "autodesk": "Autodesk",
    "atlassian": "Atlassian",
    "github": "GitHub",
    "jetbrains": "JetBrains",
    "sap se": "SAP",
    "sap": "SAP",
    "salesforce": "Salesforce",
    "canva": "Canva",
    "dropbox": "Dropbox",
    "box.com": "Box",

    # ── Streaming & Unterhaltung ─────────────────────────────────────────────
    "netflix": "Netflix",
    "spotify ab": "Spotify",
    "spotify": "Spotify",
    "apple music": "Apple-Music",
    "youtube premium": "YouTube-Premium",
    "twitch": "Twitch",
    "steam": "Steam",
    "playstation network": "PlayStation-Network",
    "nintendo": "Nintendo",
    "xbox": "Xbox",

    # ── Zahlungsdienste & FinTech ────────────────────────────────────────────
    "klarna bank": "Klarna",
    "klarna": "Klarna",
    "paypal europe": "PayPal",
    "paypal": "PayPal",
    "stripe payments": "Stripe",
    "stripe": "Stripe",
    "sumup": "SumUp",
    "n26": "N26",
    "revolut": "Revolut",
    "wise": "Wise",
    "transferwise": "Wise",
    "check24": "Check24",
    "verivox": "Verivox",
    "finanzcheck": "Finanzcheck",
    "smava": "Smava",
    "auxmoney": "Auxmoney",

    # ── Energie & Versorger ──────────────────────────────────────────────────
    "e.on energie": "EON",
    "e.on": "EON",
    "e.on se": "EON",
    "enbw energie": "EnBW",
    "enbw": "EnBW",
    "rwe ag": "RWE",
    "rwe": "RWE",
    "vattenfall": "Vattenfall",
    "badenova": "Badenova",
    "naturstrom": "Naturstrom",
    "yello strom": "Yello",
    "yello": "Yello",
    "stadtwerke": "Stadtwerke",
    "energie wasser": "Stadtwerke",
    "gasag": "GASAG",
    "swm": "SWM",
    "ewe": "EWE",
    "innogy": "Innogy",
    "westnetz": "Westnetz",
    "bayernwerk": "Bayernwerk",
    "netz bw": "Netz-BW",
    "netze bw": "Netz-BW",
    "e.dis": "E.DIS",
    "edis": "E.DIS",
    "avacon": "Avacon",
    "stromnetz berlin": "Stromnetz-Berlin",
    "enviam": "enviaM",
    "ew medl": "MEDL",
    "maingau energie": "Maingau",
    "lew": "LEW",
    "maxenergy": "Maxenergy",
    "sonnen": "Sonnen",
    "tibber": "Tibber",
    "aWATTar": "aWATTar",

    # ── Wasser / Gas ─────────────────────────────────────────────────────────
    "gelsenwasser": "Gelsenwasser",
    "fernwärme": "Fernwaerme",
    "gasversorgung": "Gasversorgung",

    # ── Paket & Logistik ─────────────────────────────────────────────────────
    "deutsche post ag": "Deutsche-Post",
    "deutsche post": "Deutsche-Post",
    "dhl paket": "DHL",
    "dhl express": "DHL",
    "dhl": "DHL",
    "dpd gmbh": "DPD",
    "dpd": "DPD",
    "gls pakete": "GLS",
    "gls": "GLS",
    "hermes europe": "Hermes",
    "hermes": "Hermes",
    "ups": "UPS",
    "fedex": "FedEx",
    "tnt": "TNT",
    "amazon logistics": "Amazon-Logistics",

    # ── Mobilität & Kfz ─────────────────────────────────────────────────────
    "deutsche bahn ag": "Deutsche-Bahn",
    "deutsche bahn": "Deutsche-Bahn",
    "db vertrieb": "Deutsche-Bahn",
    "db regio": "DB-Regio",
    "db fernverkehr": "DB-Fernverkehr",
    "flixbus": "FlixBus",
    "flixtrain": "FlixTrain",
    "lufthansa": "Lufthansa",
    "eurowings": "Eurowings",
    "condor": "Condor",
    "ryanair": "Ryanair",
    "easyjet": "EasyJet",
    "uber": "Uber",
    "free now": "FreeNow",
    "sixt": "Sixt",
    "enterprise autovermietung": "Enterprise",
    "enterprise": "Enterprise",
    "hertz": "Hertz",
    "avis": "Avis",
    "europcar": "Europcar",
    "dekra": "DEKRA",
    "tüv rheinland": "TUV-Rheinland",
    "tüv süd": "TUV-Sued",
    "tüv nord": "TUV-Nord",
    "tüv hessen": "TUV-Hessen",

    # ── Gesundheit & Apotheke ────────────────────────────────────────────────
    "apotheke": "Apotheke",
    "docmorris": "DocMorris",
    "shop-apotheke": "Shop-Apotheke",
    "shop apotheke": "Shop-Apotheke",
    "zur rose": "Zur-Rose",
    "dm drogerie": "dm",
    "rossmann": "Rossmann",
    "doctolib": "Doctolib",
    "jameda": "Jameda",
    "fresenius": "Fresenius",

    # ── Supermarkt & Lebensmittel ────────────────────────────────────────────
    "rewe": "REWE",
    "edeka": "EDEKA",
    "lidl": "Lidl",
    "aldi": "Aldi",
    "penny": "Penny",
    "netto": "Netto",
    "norma": "Norma",
    "real": "Real",
    "metro": "Metro",
    "globus": "Globus",

    # ── Hausverwaltung / Immobilien ──────────────────────────────────────────
    "hausverwaltung": "Hausverwaltung",
    "wohnungsbaugesellschaft": "Wohnungsbaugesellschaft",
    "wohnungsgenossenschaft": "Wohnungsgenossenschaft",
    "immobilien": "Immobilien",
    "vonovia se": "Vonovia",
    "vonovia": "Vonovia",
    "deutsche wohnen": "Deutsche-Wohnen",
    "grand city property": "GCP",
    "lew wohnbau": "LEW-Wohnbau",
    "gag immobilien": "GAG",
    "saga": "SAGA",
    "ista": "Ista",
    "techem": "Techem",
    "brunata": "Brunata",
    "minol": "Minol",
    "kalorimeta": "Kalorimeta",
    "engelvoelkers": "Engel-Voelkers",
    "engel & völkers": "Engel-Voelkers",

    # ── Steuer / Recht / Beratung ─────────────────────────────────────────────
    "lohnsteuerhilfe": "Lohnsteuerhilfe",
    "steuerberatung": "Steuerberatung",
    "notar": "Notar",
    "rechtsanwalt": "Rechtsanwalt",
    "inkasso": "Inkasso",
    "coeo inkasso": "Coeo-Inkasso",
    "inkasso büro": "Inkasso",
    "hoist finance": "Hoist-Finance",
    "intrum": "Intrum",
    "creditreform": "Creditreform",
    "schufa": "SCHUFA",
    "boniversum": "Boniversum",
    "arvato financial solutions": "Arvato",
    "arvato": "Arvato",
    "eos group": "EOS",
    "lowell": "Lowell",
    "universum group": "Universum",

    # ── Bildung & Weiterbildung ──────────────────────────────────────────────
    "volkshochschule": "VHS",
    "vhs": "VHS",
    "fernuniversität": "FernUniversitaet",
    "fernuni": "FernUniversitaet",
    "iubh": "IUBH",
    "iu internationale hochschule": "IU",
    "fom hochschule": "FOM",
    "sgd": "SGD",
    "euro fernakademie": "Euro-Fernakademie",
    "haufe akademie": "Haufe-Akademie",
    "udemy": "Udemy",
    "coursera": "Coursera",
    "linkedin learning": "LinkedIn-Learning",
    "fahrschule": "Fahrschule",
    "dekra akademie": "DEKRA-Akademie",
    "bfw": "BFW",
    "materna": "Materna",

    # ── Sport & Freizeit ─────────────────────────────────────────────────────
    "mcfit": "McFit",
    "john reed": "John-Reed",
    "fitx": "FitX",
    "fitness first": "Fitness-First",
    "clever fit": "CleverFit",
    "california fitness": "California-Fitness",
    "urban sports club": "Urban-Sports-Club",
    "adidas": "Adidas",
    "nike": "Nike",
    "intersport": "Intersport",
    "sport scheck": "SportScheck",
    "decathlon": "Decathlon",
    "ikea": "IKEA",
    "obi": "OBI",
    "bauhaus": "Bauhaus",
    "hornbach": "Hornbach",
    "toom": "Toom",
    "hagebaumarkt": "Hagebaumarkt",

    # ── Gastronomie & Lieferung ──────────────────────────────────────────────
    "lieferando": "Lieferando",
    "just eat": "Lieferando",
    "doordash": "DoorDash",
    "wolt": "Wolt",
    "deliveroo": "Deliveroo",

    # ── Mode & Lifestyle ─────────────────────────────────────────────────────
    "h&m": "H&M",
    "zara": "Zara",
    "primark": "Primark",
    "c&a": "C&A",
    "peek & cloppenburg": "P&C",
    "hugo boss": "Hugo-Boss",
    "s.oliver": "S.Oliver",
    "tom tailor": "Tom-Tailor",

    # ── Elektronik & Technik ─────────────────────────────────────────────────
    "samsung electronics": "Samsung",
    "samsung": "Samsung",
    "lg electronics": "LG",
    "sony deutschland": "Sony",
    "sony": "Sony",
    "philips": "Philips",
    "bosch": "Bosch",
    "siemens": "Siemens",
    "miele": "Miele",
    "aeg": "AEG",
    "whirlpool": "Whirlpool",
    "beko": "Beko",
    "dyson": "Dyson",
    "garmin": "Garmin",
    "fitbit": "Fitbit",
}

# Abschlussformeln, nach denen der Bewerber-Name steht
_RE_GRUSSFORMEL = re.compile(
    r'(?:Mit\s+freundlichen?\s+Gr[üu][ß]en?|'
    r'Hochachtungsvoll|'
    r'Mit\s+freundlichen?\s+Gr[üu][ß]en?|'
    r'Freundliche\s+Gr[üu][ß]e|'
    r'Viele\s+Gr[üu][ß]e|'
    r'MfG)\s*[\n\r]+',
    re.IGNORECASE,
)

# Einfacher Name: 2–4 Wörter, nur Buchstaben/Bindestrich
_RE_NAME = re.compile(r'^[A-ZÄÖÜ][a-zA-ZäöüÄÖÜß\-]+(?: [A-ZÄÖÜ][a-zA-ZäöüÄÖÜß\-]+){1,3}$')


def _extract_bewerber_name(lines: list[str], space_replacement: str = "-") -> str:
    """
    Extrahiert den Namen eines Bewerbers aus:
    1. Den Zeilen nach der Grußformel (Unterschriftsblock)
    2. Den ersten 4 Zeilen des Dokuments (Absender-Adressblock oben rechts)
    """
    full_text = "\n".join(lines)

    # Strategie 1: Name nach Grußformel
    m = _RE_GRUSSFORMEL.search(full_text)
    if m:
        rest = full_text[m.end():]
        for line in rest.split("\n"):
            candidate = line.strip()
            # Leerzeilen und sehr kurze Zeilen (Unterschrift-Bild etc.) überspringen
            if len(candidate) < 4:
                continue
            # Typische Unterschrifts-Artefakte überspringen
            if re.match(r'^[^a-zA-ZÄÖÜäöü]', candidate):
                continue
            if _RE_NAME.match(candidate):
                return clean(candidate, space_replacement)
            # Auch "Vorname\nNachname" über zwei Zeilen fangen
            break

    # Strategie 2: Erste Zeile des Dokuments die wie ein Name aussieht
    # (typisch: Absender-Block oben rechts bei privatem Anschreiben)
    for line in lines[:6]:
        candidate = line.strip()
        if _RE_NAME.match(candidate):
            return clean(candidate, space_replacement)

    return ""


def _extract_sender(text: str, space_replacement: str = "-", custom_senders: dict | None = None) -> str:
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    tl = text.lower()
    first_30 = "\n".join(lines[:30]).lower()

    # 1. Benutzerdefinierte Absender (Einstellungen) – höchste Priorität, ganzer Text
    for key, name in (custom_senders or {}).items():
        if key.lower() in tl:
            return clean(name, space_replacement)

    # 2. Behörden – erste 30 Zeilen
    for key, name in BEKANNTE_BEHOERDEN.items():
        if key in first_30:
            return clean(name, space_replacement)

    # 3. Bekannte Marken/Branchen – erst in den ersten 30 Zeilen (Briefkopf),
    #    dann Fallback auf den gesamten Text (Brieffuß, Impressum, OCR-Reihung).
    # Für Keys ≤ 4 Zeichen wird Word-Boundary geprüft (verhindert z.B.
    # "lbs" in "selbstverständlich" oder "ewe" in "bewerbung").
    for key, canonical in BEKANNTE_BRANCHEN.items():
        if len(key) <= 4:
            matched_in_first30 = bool(re.search(r'\b' + re.escape(key) + r'\b', first_30))
        else:
            matched_in_first30 = key in first_30
        if matched_in_first30:
            # Zeile finden, die den Begriff enthält
            for line in lines[:30]:
                ll = line.lower()
                hit = (re.search(r'\b' + re.escape(key) + r'\b', ll)
                       if len(key) <= 4 else key in ll)
                if hit and 3 < len(line) <= 120:
                    # Enthält die Zeile Adressdaten (PLZ, Postfach, Straße…)?
                    # Dann nur den kanonischen Kurznamen zurückgeben, nicht die
                    # ganze Adresszeile ("Volksbank Freiburg eG . Postfach 540 . 79005 Freiburg")
                    if _RE_ADDRESS.search(line):
                        return clean(canonical, space_replacement)
                    cleaned = clean(line[:80], space_replacement)
                    return cleaned if cleaned else clean(canonical, space_replacement)
            return clean(canonical, space_replacement)

    # 3b. Fallback: BEKANNTE_BRANCHEN im gesamten Text.
    #     Greift z.B. wenn der Briefkopf als Bild eingebettet ist (pdfplumber
    #     liest dann nur den Textteil ab Zeile 30+) oder wenn der Firmenname
    #     nur im Brieffuß steht. Gibt immer den kanonischen Kurznamen zurück.
    # Achtung: Für Keys ≤ 4 Zeichen wird Word-Boundary geprüft (verhindert
    #          Substring-Matches wie "ewe" in "bewerbung" oder "dm" in "damen").
    _BEWERBUNG_KEYS = ["bewerbung", "motivationsschreiben", "lebenslauf",
                       "curriculum vitae", "arbeitszeugnis", "zwischenzeugnis"]
    if not any(k in tl for k in _BEWERBUNG_KEYS):
        for key, canonical in BEKANNTE_BRANCHEN.items():
            if len(key) <= 4:
                if re.search(r'\b' + re.escape(key) + r'\b', tl):
                    return clean(canonical, space_replacement)
            else:
                if key in tl:
                    return clean(canonical, space_replacement)

    # 3c. Bewerbungs-Dokumente: Bewerber-Name aus Signatur oder Absenderblock
    # _BEWERBUNG_KEYS ist bereits oben in 3b definiert
    _BEWERBUNG_KEYS = ["bewerbung", "motivationsschreiben", "lebenslauf",
                       "curriculum vitae", "arbeitszeugnis", "zwischenzeugnis"]
    if any(k in tl for k in _BEWERBUNG_KEYS):
        name = _extract_bewerber_name(lines, space_replacement)
        return name if name else "Bewerber"

    # 4. Heuristik: Zeile mit Unternehmens-Suffix in ersten 30 Zeilen
    for line in lines[:30]:
        ll = line.lower()
        if any(s in ll for s in _COMPANY_SUFFIXES) and len(line) <= 80:
            return clean(line[:70], space_replacement)

    # 5. Erste sinnvolle Großbuchstaben-Zeile – Adress- und Empfängerzeilen
    #    werden herausgefiltert, damit nicht der Kundenname als Absender landet.
    _SKIP = {"rechnung", "datum", "betreff", "subject", "seite", "page",
             "sehr geehrte", "hiermit", "anlage", "ihre", "unser",
             "herr", "frau", "herrn", "ich ", " ich ", "mich", "wir ",
             "bitte", "gerne", "leider", "daher", "sowie", "wobei",
             "bewerbung", "lebenslauf", "motivationsschreiben"}
    for line in lines[:20]:
        if len(line) < 4 or len(line) > 60:
            continue
        if line[0].isdigit():
            continue
        ll = line.lower()
        if any(w in ll for w in _SKIP):
            continue
        # Zeilen mit mehr als 4 Wörtern sind Fließtext, kein Firmenname
        if len(line.split()) > 4:
            continue
        if _RE_ADDRESS.search(line):
            continue
        if line[0].isupper():
            return clean(line[:45], space_replacement)

    return "Unbekannt"


def _extract_subject(text: str, space_replacement: str = "-", custom_doc_types: dict | None = None) -> str:
    # ── 1. Strukturierte Muster (Rechnungsnummer, AZ, etc.) ─────────────────
    patterns = [
        (r"Rechnung(?:snummer)?[:\s#]*([A-Z]{0,3}[\d][\d\-/]{3,20})", "Rechnung-{}"),
        (r"Az\.[:\s]*([^\n\r]{3,30})", "Az-{}"),
        (r"Aktenzeichen[:\s]*([^\n\r]{3,30})", "Az-{}"),
        (r"Schaden(?:nummer)?[:\s#-]*([\d\-/]{5,20})", "Schaden-{}"),
        (r"Police\s*Nr\.?\s*([\d\s]{6,20})", "Police-{}"),
        (r"Vertrag\s+(\d{5,12})", "Vertrag-{}"),
        (r"Versicherungsschein(?:nummer)?[:\s]*([\d\-/]{5,20})", "Versicherungsschein-{}"),
    ]
    for pattern, fmt in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = clean(m.group(1).strip()[:30], space_replacement)
            return fmt.format(val)

    tl = text.lower()

    # ── 2. Bewerbungs-Erkennung: Betreffzeile auswerten ─────────────────────
    _BEWERBUNG_SUBJECT_KEYS = [
        "bewerbung", "bewerbungsunterlagen", "motivationsschreiben",
        "lebenslauf", "curriculum vitae", "arbeitszeugnis", "zwischenzeugnis",
    ]
    if any(k in tl for k in _BEWERBUNG_SUBJECT_KEYS):
        stelle = _extract_bewerbung_stelle(text, space_replacement)
        if stelle:
            return f"Bewerbung-{stelle}"
        return "Bewerbung"

    # ── 3. Keyword-Matching mit Word-Boundary (verhindert Teilwort-Treffer) ──
    # Benutzerdefinierte Dokumenttypen haben Vorrang
    for key, name in (custom_doc_types or {}).items():
        if re.search(r'\b' + re.escape(key.lower()) + r'\b', tl):
            return clean(name, space_replacement)
    # Eingebaute Liste: erst Betreff-Block (erste 5 Zeilen), dann Volltext
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    subject_block = "\n".join(lines[:5]).lower()
    for key, name in DOKUMENTTYPEN.items():
        if re.search(r'\b' + re.escape(key) + r'\b', subject_block):
            return name
    for key, name in DOKUMENTTYPEN.items():
        if re.search(r'\b' + re.escape(key) + r'\b', tl):
            return name

    return "Dokument"


# Regex zum Erkennen der Betreffzeile in Anschreiben
_RE_BETREFF = re.compile(
    r"""
    (?:Betreff\s*:\s*|                         # explizites "Betreff:"
    (?:Bewerbung|Kündigung|Antrag|Anfrage)      # oder Zeile beginnt mit Schlüsselwort
    \s+(?:um|als|für|zur|zum|auf|fuer|wegen)\b  # + Präposition
    )
    (.{5,120})                                  # Betreff-Inhalt
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Schlüsselwörter, die direkt auf die Stelle hinweisen
_RE_STELLE = re.compile(
    r"""
    (?:
        ausbildungsplatz\s+(?:als|zum?|zur?)\s+|
        stelle\s+(?:als|zum?|zur?)\s+|
        position\s+(?:als|zum?|zur?)\s+|
        (?:als|zum?|zur?)\s+                   # einfaches "als Entwickler"
    )
    ([A-ZÄÖÜ][a-zäöüßA-ZÄÖÜ\-/\s]{3,50})     # die eigentliche Stellenbezeichnung
    """,
    re.VERBOSE,
)


def _extract_bewerbung_stelle(text: str, space_replacement: str = "-") -> str:
    """Extrahiert die Stellenbezeichnung aus einer Bewerbung (max. 35 Zeichen)."""
    # Suche zuerst in einer expliziten Betreffzeile
    m_betreff = _RE_BETREFF.search(text)
    search_text = m_betreff.group(1) if m_betreff else text

    m_stelle = _RE_STELLE.search(search_text)
    if m_stelle:
        stelle = m_stelle.group(1).strip()
        # Langzeilen abschneiden (z.B. "Karosserie- und Fahrzeugbaumechaniker")
        # → erstes Wort wenn > 35 Zeichen, sonst komplett
        stelle = stelle[:35].strip()
        # Trailingzeichen bereinigen (z.B. angerissenes Wort)
        stelle = re.sub(r'[\s\-und]+$', '', stelle)
        return clean(stelle, space_replacement) if stelle else ""
    return ""


def unique_path(folder: str, filename: str, strategy: str = "suffix") -> str:
    """Gibt eindeutigen Zielpfad zurueck (Suffix _2/_3 oder Ueberschreiben)."""
    import os
    path = os.path.join(folder, filename)
    if not os.path.exists(path):
        return path
    if strategy == "overwrite":
        return path
    stem, ext = os.path.splitext(filename)
    i = 2
    while True:
        candidate = os.path.join(folder, f"{stem}_{i}{ext}")
        if not os.path.exists(candidate):
            return candidate
        i += 1
