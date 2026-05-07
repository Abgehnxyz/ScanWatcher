# Scan Watcher
**Nova Network** – Automatische PDF-Umbenennung fuer Scan-Eingangskoerbe

## Was es macht
Scan Watcher ueberwacht einen lokalen Scan-Ordner. Sobald der Scanner eine neue
Datei mit reinem Zahlennamen ablegt (z.B. `202605070001.pdf`), wird sie
automatisch per OCR analysiert, sinnvoll umbenannt und ins Archiv verschoben.

**Beispiel:**
`202605070001.pdf` → `2026-04-22_KRAVAG_Police-407-85-350295747_Betriebsschutz.pdf`

## Voraussetzungen
- Windows 10/11 (64-bit)
- [Python 3.11+](https://python.org/downloads)
- [Tesseract-OCR fuer Windows](https://github.com/UB-Mannheim/tesseract/wiki)

## Installation (Entwicklung)
```
py -m pip install -r requirements.txt
```

## Starten
```
py run.py
```
Beim ersten Start oeffnet sich automatisch der Einstellungs-Dialog.

## Projektstruktur
```
scan-watcher/
├── src/
│   ├── main.py            # Einstiegspunkt
│   ├── tray.py            # System-Tray-Icon
│   ├── settings_dialog.py # Einstellungs-Fenster
│   ├── watcher.py         # Dateiueberwachung
│   ├── ocr.py             # Text-Extraktion (pdfplumber + Tesseract)
│   ├── renamer.py         # Namens-Bestimmung (Regeln + opt. Claude API)
│   └── config.py          # Konfigurationsverwaltung
├── assets/
│   └── icon.png           # App-Icon (64x64, RGBA)
├── installer/
│   └── setup.iss          # Inno Setup Installer-Skript
├── tests/
│   └── test_renamer.py    # Unit-Tests
├── run.py                 # Start & PyInstaller-Einstieg
├── build.bat              # EXE + Installer bauen
└── requirements.txt
```

## EXE bauen
```
build.bat
```
Ergebnis: `dist/ScanWatcher/ScanWatcher.exe` + `dist/installer/ScanWatcher_Setup_v1.0.0.exe`

Benoetigt [Inno Setup 6](https://jrsoftware.org/isdl.php) fuer den Installer.

## Konfiguration
Einstellungen werden gespeichert in:
`%APPDATA%\ScanWatcher\config.json`

| Einstellung | Beschreibung |
|---|---|
| `source_folder` | Scan-Ordner (lokal, z.B. D:\Scan) |
| `target_folder` | Ziel-Ordner (Netzwerk oder lokal) |
| `tesseract_exe` | Pfad zur tesseract.exe |
| `anthropic_key` | Claude API-Key (optional, verbessert Benennung) |

## Lizenz
Proprietaer – Nova Network. Alle Rechte vorbehalten.
