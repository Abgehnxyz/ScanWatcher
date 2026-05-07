"""
@file    renamer.py
@project Scan Watcher
@company Nova Network GmbH
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


def clean(text: str) -> str:
    """Sonderzeichen fuer Dateinamen normalisieren."""
    replacements = {
        "ae": ["ä"], "oe": ["ö"], "ue": ["ü"],
        "Ae": ["Ä"], "Oe": ["Ö"], "Ue": ["Ü"],
        "ss": ["ß"], "-": [" ", "/", "\\"],
        "": [":", ";", ",", '"', "'", "(", ")", "[", "]", "!", "?"],
        "u": ["&"],
    }
    for new, olds in replacements.items():
        for old in olds:
            text = text.replace(old, new)
    text = re.sub(r"[^A-Za-z0-9\-_]", "", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-")


def determine_name(
    text: str,
    original_filename: str,
    anthropic_key: str = "",
    ollama_enabled: bool = False,
    ollama_model: str = "llama3.2",
) -> str:
    """Dateinamen bestimmen – Reihenfolge: Claude API → Ollama → Regeln."""
    if anthropic_key:
        name = _via_claude(text, original_filename, anthropic_key)
        if name:
            return name
    if ollama_enabled:
        name = _via_ollama(text, original_filename, ollama_model)
        if name:
            return name
    return _via_rules(text, original_filename)


def _via_claude(text: str, original_filename: str, api_key: str) -> str | None:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key, timeout=30.0)
        prompt = f"""Bestimme fuer dieses gescannte Dokument den Dateinamen.
Schema: DATUM_Absender_Betreff (ohne .pdf)
Regeln: Umlaute ersetzen (ae/oe/ue/ss), Leerzeichen zu Bindestrich, max 120 Zeichen.
Nur den Dateinamen, kein Erklaerungstext.

Beispiele:
2026-04-01_inView_Rechnung-RE10154_VW-Golf-Totalschaden
2026-03-25_Arbeitsgericht-Freiburg_Az-2Ca113-26_Guetetermin
2026-04-22_KRAVAG_Police-407-85-350295747_Betriebsschutz-2-Erinnerung

OCR-Text:
{text[:3000]}"""
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


def _via_ollama(text: str, original_filename: str, model: str) -> str | None:
    """Dateinamen per lokalem Ollama-Modell bestimmen (kein Internet noetig)."""
    import json
    import urllib.request

    prompt = (
        "Bestimme fuer dieses gescannte Dokument den Dateinamen.\n"
        "Schema: DATUM_Absender_Betreff (ohne .pdf)\n"
        "Regeln: Umlaute ersetzen (ae/oe/ue/ss), Leerzeichen zu Bindestrich, max 120 Zeichen.\n"
        "Nur den Dateinamen zurueckgeben, kein Erklaerungstext, keine Anfuehrungszeichen.\n\n"
        "Beispiele:\n"
        "2026-04-01_inView_Rechnung-RE10154\n"
        "2026-03-25_Arbeitsgericht-Freiburg_Guetetermin\n"
        "2026-04-22_KRAVAG_Police-407-Betriebsschutz-Erinnerung\n\n"
        f"OCR-Text:\n{text[:3000]}"
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


def _via_rules(text: str, original_filename: str) -> str:
    datum = _extract_date(text, original_filename)
    absender = _extract_sender(text)
    betreff = _extract_subject(text)
    log.info("  Benennung: Lokale Regeln")
    return f"{datum}_{absender}_{betreff}"[:120]


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


def _extract_sender(text: str) -> str:
    tl = text.lower()
    for key, name in BEKANNTE_ABSENDER.items():
        if key in tl:
            return clean(name)
    # Erste sinnvolle Zeile als Fallback
    for line in text.split("\n")[:8]:
        line = line.strip()
        if len(line) > 3 and line[0].isupper() and not line[0].isdigit():
            return clean(line[:35])
    return "Unbekannt"


def _extract_subject(text: str) -> str:
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
            val = clean(m.group(1).strip()[:30])
            return fmt.format(val)

    # Dokumenttyp-Erkennung
    tl = text.lower()
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
