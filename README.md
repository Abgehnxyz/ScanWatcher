# Scan Watcher

**by Nova Network** – Automatic OCR-based renaming for scanned documents on Windows

[![Release](https://img.shields.io/github/v/release/Abgehnxyz/ScanWatcher)](https://github.com/Abgehnxyz/ScanWatcher/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Support on Ko-fi](https://img.shields.io/badge/Ko--fi-Support-29abe0)](https://ko-fi.com/novanetwork)

---

![Scan Watcher Screenshot](pictures/Scan_Watcher.png)

---

## What it does

Scan Watcher runs silently in the Windows system tray and watches a folder. When your scanner drops a new PDF with a generic filename like `SCAN_20260512_143201.pdf`, Scan Watcher reads it via OCR, identifies the sender and document type, and renames it automatically.

**Example:**
```
SCAN_20260512_143201.pdf  →  2026-05-08_Apple_Invoice.pdf
```

---

## Features

| Feature | Description |
|---------|-------------|
| **OCR** | pdfplumber (text layer) + Tesseract (scanned images) with image preprocessing |
| **AI renaming** | Claude, GPT-4o-mini, Gemini, Mistral, Groq or local Ollama models |
| **Rule-based** | Works without AI – recognizes 250+ senders, dates and document types |
| **Custom schema** | Fully configurable naming template: `{DATE}_{SENDER}_{SUBJECT}` |
| **Multiple profiles** | Watch multiple source→target folder pairs simultaneously |
| **Confidence check** | Low-confidence OCR results get a `PRUEFEN_` prefix automatically |
| **System tray** | Runs in the background with a tray icon and status display |
| **Auto-updater** | Checks for new releases on startup, in-app installer download |
| **Telemetry** | GDPR-compliant, anonymous opt-in, disabled by default |

---

## Installation

1. Download the latest installer from [Releases](https://github.com/Abgehnxyz/ScanWatcher/releases/latest)
2. Run `ScanWatcher_Setup_vX.X.X.exe`
3. Scan Watcher starts automatically after installation

**Requirements:** Windows 10/11 (64-bit) — no additional software needed, everything is bundled.

---

## Development setup

### Prerequisites
- Python 3.11+
- [Tesseract-OCR for Windows](https://github.com/UB-Mannheim/tesseract/wiki) (including German language pack)

### Setup
```powershell
git clone https://github.com/Abgehnxyz/ScanWatcher.git
cd ScanWatcher
py -m pip install -r requirements.txt
py run.py
```

On first run, the settings dialog opens automatically.

---

## AI models

Scan Watcher supports the following renaming modes:

| Mode | Cost | Internet | Setup |
|------|------|----------|-------|
| **Rule-based** | free | no | none |
| **Ollama (local)** | free | no | [Install Ollama](https://ollama.com) |
| **Claude (Haiku)** | ~$0.001/doc | yes | [API key](https://console.anthropic.com) |
| **GPT-4o-mini** | ~$0.001/doc | yes | [API key](https://platform.openai.com) |
| **Gemini Flash** | free tier | yes | [API key](https://aistudio.google.com) |
| **Mistral Small** | ~$0.001/doc | yes | [API key](https://console.mistral.ai) |
| **Groq** | free tier | yes | [API key](https://console.groq.com) |

API keys are stored encrypted in the **Windows Credential Manager**.

---

## Building from source

```bat
build.bat
```

Output:
- `dist/ScanWatcher/ScanWatcher.exe`
- `dist/installer/ScanWatcher_Setup_vX.X.X.exe`

Requires [Inno Setup 6](https://jrsoftware.org/isdl.php) for the installer.

---

## Configuration

Settings are saved at:
```
%APPDATA%\ScanWatcher\config.json
```

All settings are accessible via the settings dialog (tray icon → right-click → Settings).

---

## Project structure

```
scan-watcher/
├── .github/workflows/
│   └── release.yml        # Auto-build on tag push
├── src/
│   ├── main.py            # Entry point
│   ├── tray.py            # System tray & UI
│   ├── settings_dialog.py # Settings dialog
│   ├── watcher.py         # File watcher (watchdog)
│   ├── ocr.py             # OCR (pdfplumber + Tesseract + PIL)
│   ├── renamer.py         # Naming logic (rules + AI)
│   ├── updater.py         # GitHub update check
│   ├── telemetry.py       # Anonymous opt-in telemetry
│   └── config.py          # Configuration management
├── assets/
│   └── icon.png
├── installer/
│   └── setup.iss          # Inno Setup script
├── tests/
│   └── test_renamer.py
├── run.py
├── build.bat
└── requirements.txt
```

---

## License

MIT License – see [LICENSE](LICENSE)

---

## Support

Scan Watcher is free and open source.  
If it saves you time, a coffee is always appreciated:

**[☕ ko-fi.com/novanetwork](https://ko-fi.com/novanetwork)**
