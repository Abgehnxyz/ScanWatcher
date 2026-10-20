# Scan Watcher

**by Nova Network** – Automatic OCR-based renaming for scanned documents on Windows

[![Release](https://img.shields.io/github/v/release/Abgehnxyz/ScanWatcher)](https://github.com/Abgehnxyz/ScanWatcher/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Support on Ko-fi](https://img.shields.io/badge/Ko--fi-Support-29abe0)](https://ko-fi.com/novanetwork)

---

![Scan Watcher Screenshot](pictures/Scan_Watcher.png)

---

## What it does

Scan Watcher runs silently in the Windows system tray and watches a folder. When your scanner drops a new file with a generic numeric name like `20260512143201.pdf`, Scan Watcher reads it via OCR, identifies the sender and document type, and renames it automatically.

**Example:**
```
20260512143201.pdf  →  2026-05-08_Apple_Rechnung.pdf
```

By default only purely numeric file names are picked up. If your scanner uses a different naming scheme (e.g. `SCAN_20260512_143201.pdf`), set a matching regular expression under *Settings → Watcher → Name pattern*, for example `SCAN_\d+_\d+`.

Document types and the user interface are in German.

---

## Features

| Feature | Description |
|---------|-------------|
| **OCR** | pdfplumber (text layer) + bundled Tesseract (scanned images, multi-page TIFF) with image preprocessing |
| **AI renaming** | Your choice: local Ollama, any OpenAI-compatible server (LM Studio, vLLM, OpenRouter …) or Claude, OpenAI, Gemini, Mistral, Groq – the AI only extracts date, sender and subject; the file name is always built locally |
| **Rule-based** | Works without AI – recognizes 500+ senders, dates and document types |
| **Custom schema** | Configurable naming template with sub-folders, e.g. `{JAHR}/{DATUM}_{ABSENDER}_{BETREFF}` |
| **Multiple profiles** | Watch multiple source→target folder pairs simultaneously |
| **Confidence check** | Low-confidence OCR results get a `PRUEFEN_` prefix automatically |
| **System tray** | Runs in the background with a tray icon and status display, dark and light mode |
| **Auto-updater** | Checks GitHub for new releases, downloads the installer and verifies its SHA-256 checksum |
| **Telemetry** | GDPR-compliant, anonymous opt-in, disabled by default |

---

## Installation

1. Download the latest installer from [Releases](https://github.com/Abgehnxyz/ScanWatcher/releases/latest)
2. Run `ScanWatcher_Setup_vX.X.X.exe`
3. Scan Watcher starts automatically after installation

**Requirements:** Windows 10/11 (64-bit) — no additional software needed, Tesseract OCR is bundled.

---

## Naming template

| Token | Alias | Example |
|-------|-------|---------|
| `{DATUM}` | `{DATE}` | `2026-05-08` (format selectable) |
| `{JAHR}` / `{MONAT}` / `{TAG}` | `{YEAR}` / `{MONTH}` / `{DAY}` | `2026` / `05` / `08` |
| `{ABSENDER}` | `{SENDER}` | `Telekom` |
| `{BETREFF}` | `{SUBJECT}` | `Rechnung` |
| `{ORIGINAL}` | – | original file name without extension |

A `/` in the template creates sub-folders: `{JAHR}/{MONAT}/{DATUM}_{ABSENDER}` → `2026/05/2026-05-08_Telekom.pdf`.

---

## AI models

Use whatever you already have – a local model, your own server or a cloud API:

| Mode | Default model | Cost | Data leaves your network | Setup |
|------|---------------|------|--------------------------|-------|
| **Rule-based** | – | free | no | none |
| **Ollama** (local or own server) | pick from your server | free | no | [Install Ollama](https://ollama.com) |
| **OpenAI-compatible** (any endpoint) | pick from your server | depends | depends | base URL + optional key |
| **Claude** | `claude-haiku-5-5` | < $0.001/doc | yes | [API key](https://console.anthropic.com) |
| **OpenAI** | `gpt-6-luna` | see OpenAI pricing | yes | [API key](https://platform.openai.com) |
| **Gemini** | `gemini-flash-latest` | free tier | yes | [API key](https://aistudio.google.com) |
| **Mistral** (EU) | `mistral-small-latest` | ~$0.001/doc | yes | [API key](https://console.mistral.ai) |
| **Groq** | `openai/gpt-oss-20b` | free tier | yes | [API key](https://console.groq.com) |

Every mode has a **Test connection** button in the settings: it sends a made-up sample letter and shows the resulting file name – or the exact error (server unreachable, model not found, invalid key …).

### Bring your own model

**Ollama** – enter the server address (default `http://localhost:11434`, or e.g. `192.168.1.20:11434` for a machine in your network; start Ollama there with `OLLAMA_HOST=0.0.0.0`). The model list is loaded from the server. An API key is optional, for servers behind a reverse proxy with authentication. Models with good results on German letters: `llama3.1`, `qwen2.5`, `mistral`.

**OpenAI-compatible** – works with every server that speaks the OpenAI Chat Completions API:

| Server | Base URL | API key |
|--------|----------|---------|
| LM Studio | `http://localhost:1234/v1` | – |
| vLLM | `http://<server>:8000/v1` | if configured |
| LocalAI / llama.cpp server | `http://<server>:8080/v1` | if configured |
| Ollama (OpenAI mode) | `http://localhost:11434/v1` | – |
| OpenRouter | `https://openrouter.ai/api/v1` | yes |
| DeepSeek | `https://api.deepseek.com/v1` | yes |

**Cloud providers** – the model ID can be overridden in the settings, useful when a provider retires a model before the next Scan Watcher release.

API keys are stored encrypted in the **Windows Credential Manager**, never in `config.json`. The AI only returns date, sender and subject as JSON; the file name is always built locally from your template. If an AI request fails during operation, Scan Watcher falls back to the rule-based naming and logs a warning.

---

## Privacy

- **Telemetry** is opt-in and disabled by default. When enabled, Scan Watcher sends the app version, Windows build, the naming mode used and success/failure counts – never file names or contents.
- **Notices** (e.g. about critical bug fixes) are fetched from the Nova Network server only when telemetry is enabled.
- **Update checks** contact the GitHub API and can be disabled in the settings.
- **AI renaming** sends the OCR text (up to 6,000 characters) to the selected provider. Use the rule-based mode, Ollama or a local OpenAI-compatible server to keep everything in your own network.

---

## Development setup

### Prerequisites
- Python 3.14
- [Tesseract-OCR for Windows](https://github.com/UB-Mannheim/tesseract/wiki) (including German language pack)

### Setup
```powershell
git clone https://github.com/Abgehnxyz/ScanWatcher.git
cd ScanWatcher
py -m pip install -r requirements-dev.txt
py -m pytest tests/
py run.py
```

On first run, the settings dialog opens automatically. `py run_dev.py dialog|renamer|consent` starts single components.

---

## Building from source

```bat
build.bat
```

The version is read from `src/__init__.py` (single source of truth). The script runs the tests, bundles Tesseract including its DLLs and builds the installer.

Output:
- `dist/ScanWatcher/ScanWatcher.exe`
- `dist/installer/ScanWatcher_Setup_vX.X.X.exe`

Requires [Inno Setup 6](https://jrsoftware.org/isdl.php) for the installer.

**Releases:** bump `__version__` in `src/__init__.py`, commit, then push a matching tag (`git tag v1.0.19 && git push --tags`). The GitHub workflow checks that tag and version match, runs the tests and publishes the installer with its SHA-256 checksum.

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
│   └── release.yml        # Test, build and release on tag push
├── src/
│   ├── main.py            # Entry point
│   ├── ui.py              # Single Tk thread for all windows
│   ├── theme.py           # Dark/light color palette
│   ├── tray.py            # System tray & windows
│   ├── settings_dialog.py # Settings dialog
│   ├── watcher.py         # File watcher (watchdog) + worker pool
│   ├── ocr.py             # OCR (pdfplumber + Tesseract + PIL)
│   ├── renamer.py         # Naming logic (rules + AI)
│   ├── updater.py         # GitHub update check
│   ├── telemetry.py       # Anonymous opt-in telemetry
│   └── config.py          # Configuration management
├── assets/
├── installer/
│   └── setup.iss          # Inno Setup script
├── tests/
├── run.py
├── build.bat
├── requirements.txt       # Runtime dependencies (pinned)
└── requirements-dev.txt   # Build and test dependencies
```

---

## License

MIT License – see [LICENSE](LICENSE)

---

## Support

Scan Watcher is free and open source.  
If it saves you time, a coffee is always appreciated:

**[☕ ko-fi.com/novanetwork](https://ko-fi.com/novanetwork)**
