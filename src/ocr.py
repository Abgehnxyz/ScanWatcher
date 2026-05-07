"""
@file    ocr.py
@project Scan Watcher
@company Nova Network GmbH
@date    Mai 2026
@brief   Text-Extraktion aus PDF-Dateien.
         Stufe 1: pdfplumber (digitaler Textlayer).
         Stufe 2: PyMuPDF + Tesseract OCR (gescannte Dokumente, deu/eng).
"""

import io
import logging
import os
import sys
from pathlib import Path

import fitz  # pymupdf
import pdfplumber
import pytesseract
from PIL import Image

log = logging.getLogger("scan_watcher.ocr")


def _resolve_tesseract(tesseract_exe: str) -> str:
    """Relativen Tesseract-Pfad auf absoluten Pfad aufloesen."""
    p = Path(tesseract_exe)
    if p.is_absolute() and p.exists():
        return str(p)
    # PyInstaller: _MEIPASS zeigt auf _internal/
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent.parent
    resolved = base / tesseract_exe
    if resolved.exists():
        return str(resolved)
    # Fallback: System-Tesseract
    return tesseract_exe


def extract_text(pdf_path: str, tesseract_exe: str, pages: int = 2) -> str:
    """
    Extrahiert Text aus einer PDF-Datei.
    Gibt leeren String zurueck wenn kein Text lesbar.
    """
    text = _try_pdfplumber(pdf_path, pages)
    if not text:
        text = _try_ocr(pdf_path, tesseract_exe, pages)
    return text


def _try_pdfplumber(pdf_path: str, pages: int) -> str:
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:pages]:
                t = page.extract_text()
                if t:
                    text += t + "\n"
    except Exception as e:
        log.debug(f"pdfplumber: {e}")
    return text.strip()


def _try_ocr(pdf_path: str, tesseract_exe: str, pages: int) -> str:
    text = ""
    try:
        pytesseract.pytesseract.tesseract_cmd = _resolve_tesseract(tesseract_exe)
        doc = fitz.open(pdf_path)
        for i in range(min(pages, len(doc))):
            pix = doc[i].get_pixmap(matrix=fitz.Matrix(200 / 72, 200 / 72))
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            text += pytesseract.image_to_string(img, lang="deu+eng") + "\n"
        doc.close()
        log.debug(f"OCR erfolgreich: {len(text)} Zeichen")
    except Exception as e:
        log.warning(f"OCR fehlgeschlagen: {e}")
    return text.strip()
