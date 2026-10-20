"""
@file    ocr.py
@project Scan Watcher
@company Nova Network
@date    Mai 2026
@brief   Text-Extraktion aus PDF- und Bilddateien.
         Stufe 1: pdfplumber (digitaler Textlayer).
         Stufe 2: PyMuPDF + Tesseract OCR mit optionaler Bildvorverarbeitung.
"""

import io
import logging
import sys
import winreg
from pathlib import Path
from typing import NamedTuple

import fitz  # pymupdf
import pdfplumber
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageSequence

log = logging.getLogger("scan_watcher.ocr")

_MIN_CONFIDENCE = 40  # Unter diesem Wert → PRÜFEN_-Prefix empfohlen
_MIN_TEXT_CHARS = 40  # Weniger Zeichen im Textlayer → Seite zusaetzlich per OCR lesen


class OcrResult(NamedTuple):
    text: str
    confidence: float  # 0–100, -1 wenn nicht ermittelbar


def _resolve_tesseract(tesseract_exe: str) -> str:
    p = Path(tesseract_exe)
    if p.is_absolute() and p.exists():
        return str(p)
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
        resolved = base / tesseract_exe
        if resolved.exists():
            return str(resolved)
    else:
        base = Path(__file__).parent.parent
        resolved = base / tesseract_exe
        if resolved.exists():
            return str(resolved)
        # Entwicklungsmodus: Installationspfad aus Windows-Registry lesen
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Tesseract-OCR")
            install_dir, _ = winreg.QueryValueEx(key, "InstallDir")
            winreg.CloseKey(key)
            registry_path = Path(install_dir) / "tesseract.exe"
            if registry_path.exists():
                log.debug(f"Tesseract aus Registry: {registry_path}")
                return str(registry_path)
        except OSError:
            pass
        # Letzter Fallback: System-PATH nutzen
        return "tesseract"
    return tesseract_exe


def _preprocess(img: Image.Image) -> Image.Image:
    """Kontrast- und Schaerfe-Verbesserung vor Tesseract."""
    img = img.convert("L")  # Graustufen
    img = ImageEnhance.Contrast(img).enhance(1.8)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))
    return img


def extract_text_with_confidence(
    file_path: str, tesseract_exe: str, pages: int = 2
) -> OcrResult:
    """
    Extrahiert Text und ermittelt OCR-Konfidenz.
    Bei Konfidenz < _MIN_CONFIDENCE sollte der Aufrufer PRUEFEN_-Prefix setzen.
    """
    suffix = Path(file_path).suffix.lower()
    if suffix in (".jpg", ".jpeg", ".tiff", ".tif", ".png"):
        return _try_image_ocr(file_path, tesseract_exe, pages)
    text = _try_pdfplumber(file_path, pages)
    if _has_enough_text(text):
        return OcrResult(text=text, confidence=100.0)
    # Kein oder nur winziger Textlayer (z. B. Scanner-Fusszeile "Seite 1"):
    # Seite per OCR lesen und das laengere Ergebnis nehmen.
    result = _try_ocr(file_path, tesseract_exe, pages)
    if len(result.text) >= len(text):
        return result
    return OcrResult(text=text, confidence=100.0)


def _has_enough_text(text: str) -> bool:
    return sum(c.isalnum() for c in text) >= _MIN_TEXT_CHARS


def _try_pdfplumber(pdf_path: str, pages: int) -> str:
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:pages]:
                t = page.extract_text()
                if t:
                    text += t + "\n"
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        cells = [c.strip() if isinstance(c, str) else "" for c in row]
                        line = "  |  ".join(c for c in cells if c)
                        if line:
                            text += line + "\n"
    except Exception as e:
        log.debug(f"pdfplumber: {e}")
    return text.strip()


def _ocr_image(img: Image.Image) -> tuple[str, float]:
    """Ein Tesseract-Lauf pro Bild – Text und Konfidenz aus denselben Daten."""
    data = pytesseract.image_to_data(_preprocess(img), lang="deu+eng",
                                     output_type=pytesseract.Output.DICT)
    return _text_from_data(data), _mean_confidence(data)


def _try_image_ocr(file_path: str, tesseract_exe: str, pages: int = 2) -> OcrResult:
    texts: list[str] = []
    confs: list[float] = []
    try:
        pytesseract.pytesseract.tesseract_cmd = _resolve_tesseract(tesseract_exe)
        with Image.open(file_path) as img:
            # Mehrseitige TIFFs: bis zu `pages` Seiten lesen
            for i, frame in enumerate(ImageSequence.Iterator(img)):
                if i >= pages:
                    break
                t, c = _ocr_image(frame.copy())
                texts.append(t)
                if c >= 0:
                    confs.append(c)
        text = "\n".join(texts).strip()
        conf = sum(confs) / len(confs) if confs else -1
        log.debug(f"Bild-OCR: {len(text)} Zeichen, Konfidenz: {conf:.0f}%")
        return OcrResult(text=text, confidence=conf)
    except Exception as e:
        log.warning(f"Bild-OCR fehlgeschlagen: {e}")
        return OcrResult(text="", confidence=-1)


def _try_ocr(pdf_path: str, tesseract_exe: str, pages: int) -> OcrResult:
    texts: list[str] = []
    confs: list[float] = []
    try:
        pytesseract.pytesseract.tesseract_cmd = _resolve_tesseract(tesseract_exe)
        with fitz.open(pdf_path) as doc:
            for i in range(min(pages, len(doc))):
                pix = doc[i].get_pixmap(matrix=fitz.Matrix(200 / 72, 200 / 72))
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                t, c = _ocr_image(img)
                texts.append(t)
                if c >= 0:
                    confs.append(c)
        conf = sum(confs) / len(confs) if confs else -1
    except Exception as e:
        log.warning(f"OCR fehlgeschlagen: {e}")
        conf = -1
    text = "\n".join(texts).strip()
    log.debug(f"OCR: {len(text)} Zeichen, Konfidenz: {conf:.0f}%")
    return OcrResult(text=text, confidence=conf)


def _text_from_data(data: dict) -> str:
    """Text mit Zeilenumbruechen aus Tesseract-image_to_data rekonstruieren."""
    lines: list[str] = []
    current: list[str] = []
    last_key = None
    for i, word in enumerate(data.get("text", [])):
        word = (word or "").strip()
        if not word:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        if last_key is not None and key != last_key:
            lines.append(" ".join(current))
            current = []
        current.append(word)
        last_key = key
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines)


def _mean_confidence(data: dict) -> float:
    """Mittlere Wort-Konfidenz. Je nach Version Ganz- oder Kommazahlen
    ("96.53"); -1 steht fuer Nicht-Wort-Elemente."""
    vals = []
    for c in data.get("conf", []):
        try:
            v = float(c)
        except (TypeError, ValueError):
            continue
        if v >= 0:
            vals.append(v)
    return sum(vals) / len(vals) if vals else -1


def needs_review(result: OcrResult) -> bool:
    """True wenn OCR-Konfidenz unter dem Schwellenwert liegt."""
    return 0 <= result.confidence < _MIN_CONFIDENCE
