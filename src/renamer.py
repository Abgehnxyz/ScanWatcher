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

BEKANNTE_ABSENDER = {
    "kravag-logistic": "KRAVAG", "kravag": "KRAVAG",
    "huk-coburg": "HUK-COBURG", "huk coburg": "HUK-COBURG", "huk": "HUK-COBURG",
    "allianz": "Allianz", "hdi": "HDI", "wwk": "WWK",
    "axa": "AXA", "zurich": "Zurich", "zuerick": "Zurich",
    "finanzamt": "Finanzamt", "amtsgericht": "Amtsgericht",
    "landgericht": "Landgericht", "arbeitsgericht": "Arbeitsgericht",
    "verwaltungsgericht": "Verwaltungsgericht",
    "drv": "DRV", "deutsche rentenversicherung": "DRV",
    "bundesagentur fuer arbeit": "Bundesagentur-Arbeit",
    "mercator": "MercatorLeasing", "inview": "inView",
    "raiffeisenbank": "Raiffeisenbank", "sparkasse": "Sparkasse",
    "volksbank": "Volksbank", "commerzbank": "Commerzbank",
    "badenova": "Badenova", "dekra": "DEKRA",
    "r+v": "RuV", "r&v": "RuV", "wuerttembergische": "Wuerttembergische",
    "devk": "DEVK", "generali": "Generali", "ergo": "ERGO",
}

DOKUMENTTYPEN = {
    "mahnung": "Mahnung", "2. erinnerung": "2-Erinnerung",
    "erinnerung": "Erinnerung", "rechnung": "Rechnung",
    "beitragsrechnung": "Beitragsrechnung", "bescheid": "Bescheid",
    "feststellungsbescheid": "Feststellungsbescheid",
    "bescheinigung": "Bescheinigung", "kuendigung": "Kuendigung",
    "kündigung": "Kuendigung", "ladung": "Ladung",
    "urteil": "Urteil", "gutachten": "Gutachten",
    "vollmacht": "Vollmacht", "vertrag": "Vertrag",
    "zustellungsurkunde": "Zustellungsurkunde",
    "guetetermin": "Guetetermin", "haupttermin": "Haupttermin",
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


def _extract_sender(text: str, space_replacement: str = "-", custom_senders: dict | None = None) -> str:
    tl = text.lower()
    # Benutzerdefinierte Absender haben Vorrang vor der eingebauten Liste
    for key, name in (custom_senders or {}).items():
        if key.lower() in tl:
            return clean(name, space_replacement)
    for key, name in BEKANNTE_ABSENDER.items():
        if key in tl:
            return clean(name, space_replacement)
    for line in text.split("\n")[:8]:
        line = line.strip()
        if len(line) > 3 and line[0].isupper() and not line[0].isdigit():
            return clean(line[:35], space_replacement)
    return "Unbekannt"


def _extract_subject(text: str, space_replacement: str = "-", custom_doc_types: dict | None = None) -> str:
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
    # Benutzerdefinierte Dokumenttypen haben Vorrang vor der eingebauten Liste
    for key, name in (custom_doc_types or {}).items():
        if key.lower() in tl:
            return clean(name, space_replacement)
    for key, name in DOKUMENTTYPEN.items():
        if key in tl:
            return name

    return "Dokument"


def unique_path(folder: str, filename: str) -> str:
    """Gibt eindeutigen Zielpfad zurueck (mit _2, _3 bei Konflikt)."""
    import os
    path = os.path.join(folder, filename)
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(filename)
    i = 2
    while True:
        candidate = os.path.join(folder, f"{stem}_{i}{ext}")
        if not os.path.exists(candidate):
            return candidate
        i += 1
