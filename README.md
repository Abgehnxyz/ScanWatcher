# Scan Watcher

**Nova Network** – Automatische OCR-Umbenennung für Scan-Eingangsordner unter Windows

[![Release](https://img.shields.io/github/v/release/Abgehnxyz/ScanWatcher)](https://github.com/Abgehnxyz/ScanWatcher/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Support on Ko-fi](https://img.shields.io/badge/Ko--fi-Spenden-29abe0)](https://ko-fi.com/NovaNetwork)

---

![Scan Watcher Screenshot](pictures/Scan_Watcher.png)

---

## Was es macht

Scan Watcher überwacht einen lokalen Scan-Ordner im Hintergrund.  
Sobald der Scanner eine neue Datei mit reinem Zahlennamen ablegt (z. B. `202605070001.pdf`),  
wird sie automatisch per OCR analysiert, sinnvoll umbenannt und ins Archiv verschoben.

**Beispiel:**
```
202605070001.pdf  →  2026-04-22_KRAVAG_Police-407-85-350295747.pdf
```

---

## Features

| Feature | Beschreibung |
|---------|-------------|
| **OCR-Texterkennung** | pdfplumber (Textlayer) + Tesseract (Scan) mit Bildvorverarbeitung |
| **KI-Umbenennung** | Claude, GPT-4o-mini, Gemini, Mistral, Groq oder Ollama (offline) |
| **Regelbasiert** | Funktioniert ohne KI – erkennt Absender, Datum, Dokumenttyp aus Text |
| **Benennungsschema** | Frei konfigurierbares Template: `{DATUM}_{ABSENDER}_{BETREFF}` |
| **Mehrere Ordner-Profile** | Gleichzeitig mehrere Quelle→Ziel-Paare überwachen |
| **Dateitype** | PDF, JPG, PNG, TIFF unterstützt |
| **Konfidenz-Check** | Dateien mit schlechter OCR erhalten `PRUEFEN_`-Prefix automatisch |
| **System-Tray** | Läuft im Hintergrund, Tray-Icon mit Statusanzeige |
| **Dark/Light-Mode** | customtkinter Dark- und Light-Theme |
| **Update-Check** | Automatisch beim Start, In-App-Installer-Download |
| **Telemetrie** | DSGVO-konform, anonymes Opt-in, abschaltbar |
| **Patreon-Support** | Supporter-Token deaktiviert Erinnerungs-Meldungen |

---

## Installation (Fertig-Installer)

1. Aktuelle Version unter [Releases](https://github.com/Abgehnxyz/ScanWatcher/releases/latest) herunterladen
2. `ScanWatcher_Setup_vX.X.X.exe` ausführen
3. Scan Watcher startet automatisch nach der Installation

**Systemvoraussetzungen:** Windows 10/11 (64-bit)

---

## Installation (Entwicklung)

### Voraussetzungen
- Python 3.11+
- [Tesseract-OCR für Windows](https://github.com/UB-Mannheim/tesseract/wiki) (inkl. Deutsch-Sprachpaket)

### Setup
```powershell
git clone https://github.com/Abgehnxyz/ScanWatcher.git
cd ScanWatcher
py -m pip install -r requirements.txt
py run.py
```

Beim ersten Start öffnet sich automatisch der Einstellungs-Dialog.

---

## KI-Modelle konfigurieren

Scan Watcher unterstützt folgende Benennungs-Modi:

| Modus | Kosten | Internet | Setup |
|-------|--------|----------|-------|
| **Regelbasiert** | kostenlos | nein | keins |
| **Ollama (lokal)** | kostenlos | nein | [Ollama installieren](https://ollama.com) |
| **Claude (Haiku)** | ~$0.001/Dok | ja | [API-Key](https://console.anthropic.com) |
| **GPT-4o-mini** | ~$0.001/Dok | ja | [API-Key](https://platform.openai.com) |
| **Gemini Flash** | kostenloser Tier | ja | [API-Key](https://aistudio.google.com) |
| **Mistral Small** | ~$0.001/Dok | ja | [API-Key](https://console.mistral.ai) |
| **Groq** | kostenloser Tier | ja | [API-Key](https://console.groq.com) |

API-Keys werden verschlüsselt im **Windows Credential Manager** gespeichert.

---

## EXE selbst bauen

```bat
build.bat
```

Ergebnis:
- `dist/ScanWatcher/ScanWatcher.exe`
- `dist/installer/ScanWatcher_Setup_vX.X.X.exe`

Benötigt [Inno Setup 6](https://jrsoftware.org/isdl.php) für den Installer.

---

## Konfiguration

Einstellungen werden gespeichert unter:
```
%APPDATA%\ScanWatcher\config.json
```

Die vollständige Konfiguration ist über den Einstellungs-Dialog zugänglich  
(Tray-Icon → Rechtsklick → Einstellungen).

---

## Projektstruktur

```
scan-watcher/
├── .github/workflows/
│   └── release.yml        # Auto-Build bei Tag-Push
├── src/
│   ├── main.py            # Einstiegspunkt
│   ├── tray.py            # System-Tray-Icon & UI
│   ├── settings_dialog.py # Einstellungs-Dialog
│   ├── watcher.py         # Dateiüberwachung (watchdog)
│   ├── ocr.py             # OCR (pdfplumber + Tesseract + PIL)
│   ├── renamer.py         # Namensstrategie (Regeln + KI)
│   ├── updater.py         # GitHub-Update-Check
│   ├── telemetry.py       # Anonyme Nutzungsstatistiken
│   └── config.py          # Konfigurationsverwaltung
├── assets/
│   └── icon.png
├── installer/
│   └── setup.iss          # Inno Setup Skript
├── tests/
│   └── test_renamer.py
├── run.py
├── build.bat
└── requirements.txt
```

---

## Lizenz

MIT License – siehe [LICENSE](LICENSE)

---

## Unterstützen

Scan Watcher ist kostenlos und Open Source.  
Wenn dir das Tool hilft, freuen wir uns über deine Unterstützung auf Patreon:

**[☕ ko-fi.com/NovaNetwork](https://ko-fi.com/NovaNetwork)**
