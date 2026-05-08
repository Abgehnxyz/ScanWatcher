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
from pathlib import Path
from typing import NamedTuple

import fitz  # pymupdf
import pdfplumber
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter

log = logging.getLogger("scan_watcher.ocr")

_MIN_CONFIDENCE = 40  # Unter diesem Wert → PRÜFEN_-Prefix empfohlen


class OcrResult(NamedTuple):
    text: str
    confidence: float  # 0–100, -1 wenn nicht ermittelbar


def _resolve_tesseract(tesseract_exe: str) -> str:
    p = Path(tesseract_exe)
    if p.is_absolute() and p.exists():
        return str(p)
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent.parent
    resolved = base / tesseract_exe
    if resolved.exists():
        return str(resolved)
    return tesseract_exe


def _preprocess(img: Image.Image) -> Image.Image:
    """Kontrast- und Schaerfe-Verbesserung vor Tesseract."""
    img = img.convert("L")  # Graustufen
    img = ImageEnhance.Contrast(img).enhance(1.8)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))
    return img


def extract_text(file_path: str, tesseract_exe: str, pages: int = 2) -> str:
    """Extrahiert Text (rueckwaerts-kompatibel, gibt nur String zurueck)."""
    return extract_text_with_confidence(file_path, tesseract_exe, pages).text


def extract_text_with_confidence(
    file_path: str, tesseract_exe: str, pages: int = 2
) -> OcrResult:
    """
    Extrahiert Text und ermittelt OCR-Konfidenz.
    Bei Konfidenz < _MIN_CONFIDENCE sollte der Aufrufer PRUEFEN_-Prefix setzen.
    """
    suffix = Path(file_path).suffix.lower()
    if suffix in (".jpg", ".jpeg", ".tiff", ".tif", ".png"):
        return _try_image_ocr(file_path, tesseract_exe)
    text = _try_pdfplumber(file_path, pages)
    if text:
        return OcrResult(text=text, confidence=100.0)
    return _try_ocr(file_path, tesseract_exe, pages)


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


def _try_image_ocr(file_path: str, tesseract_exe: str) -> OcrResult:
    try:
        pytesseract.pytesseract.tesseract_cmd = _resolve_tesseract(tesseract_exe)
        img = Image.open(file_path)
        img = _preprocess(img)
        data = pytesseract.image_to_data(img, lang="deu+eng",
                                         output_type=pytesseract.Output.DICT)
        text = pytesseract.image_to_string(img, lang="deu+eng")
        conf = _mean_confidence(data)
        log.debug(f"Bild-OCR: {len(text)} Zeichen, Konfidenz: {conf:.0f}%")
        return OcrResult(text=text.strip(), confidence=conf)
    except Exception as e:
        log.warning(f"Bild-OCR fehlgeschlagen: {e}")
        return OcrResult(text="", confidence=-1)


def _try_ocr(pdf_path: str, tesseract_exe: str, pages: int) -> OcrResult:
    text = ""
    confs: list[float] = []
    try:
        pytesseract.pytesseract.tesseract_cmd = _resolve_tesseract(tesseract_exe)
        doc = fitz.open(pdf_path)
        for i in range(min(pages, len(doc))):
            pix = doc[i].get_pixmap(matrix=fitz.Matrix(200 / 72, 200 / 72))
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            img = _preprocess(img)
            data = pytesseract.image_to_data(img, lang="deu+eng",
                                              output_type=pytesseract.Output.DICT)
            text += pytesseract.image_to_string(img, lang="deu+eng") + "\n"
            c = _mean_confidence(data)
            if c >= 0:
                confs.append(c)
        doc.close()
        conf = sum(confs) / len(confs) if confs else -1
        log.debug(f"OCR: {len(text)} Zeichen, Konfidenz: {conf:.0f}%")
    except Exception as e:
        log.warning(f"OCR fehlgeschlagen: {e}")
        conf = -1
    return OcrResult(text=text.strip(), confidence=conf)


def _mean_confidence(data: dict) -> float:
    vals = [int(c) for c in data.get("conf", []) if str(c).lstrip("-").isdigit() and int(c) >= 0]
    return sum(vals) / len(vals) if vals else -1


def needs_review(result: OcrResult) -> bool:
    """True wenn OCR-Konfidenz unter dem Schwellenwert liegt."""
    return 0 <= result.confidence < _MIN_CONFIDENCE
