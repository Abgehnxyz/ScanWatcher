# Scan Watcher – Feature-Roadmap & TODO

> Ziel: Professionelles Freeware-Tool für Windows, das Scan-Ordner überwacht,
> Dokumente per OCR erkennt und intelligent umbenennt.
> Veröffentlichung auf GitHub (public), Unterstützung via Patreon.

---

## 🔥 Hohe Priorität

### Benennungsschema konfigurierbar machen
- [x] Freies Format-Template im Einstellungs-Dialog (z. B. `{DATUM}_{ABSENDER}_{BETREFF}`)
  - Tokens: `{DATUM}`, `{JAHR}`, `{MONAT}`, `{TAG}`, `{ABSENDER}`, `{BETREFF}`, `{ORIGINAL}`, `{ZAEHLER}`
  - Datumsformat frei wählbar: `YYYY-MM-DD`, `DD.MM.YYYY`, `YYYYMMDD`
  - Live-Vorschau im Dialog mit Beispiel-Output
- [x] Zeichenersatz-Regeln konfigurierbar (z. B. Leerzeichen → `_` oder `-`)
- [x] Prefix/Suffix frei definierbar (über Template, z. B. `SCAN_{DATUM}_{ABSENDER}_{BETREFF}`)

### KI-Modelle erweitern
- [x] **OpenAI GPT-4o-mini** – günstig, gute DE-Unterstützung
- [x] **Google Gemini Flash** – kostenloser Tier verfügbar
- [x] **Mistral API** – europäischer Anbieter (DSGVO-freundlicher)
- [x] **Groq API** – sehr schnell, kostenloser Tier
- [x] Jedes Modell im Dialog mit Infotext, Link zur API-Key-Seite und Preis-Hinweis
- [x] API-Key pro Modell separat im Credential Manager
- [x] Modell-Auswahl: Dropdown "Aktives Modell" (keines / Claude / GPT / Gemini / Groq / Ollama)

### Telemetrie / Usage-Tracking (DSGVO-konform)
- [x] **Opt-in** beim ersten Start (explizite Zustimmung, ablösbar in Einstellungen)
- [x] Anonyme Installation-ID (UUID, kein Personenbezug)
- [x] Gemeldete Ereignisse:
  - `install` – Version, Windows-Build (kein Hostname, kein Username)
  - `rename` – Erfolg/Misserfolg, genutztes Modell, Dateianzahl
  - `heartbeat` – wöchentlich: aktive Installation, Version
  - `uninstall` – via Inno Setup Deinstallations-Hook *(ausstehend – Installer)*
- [x] Endpoint: `https://ops.abgehn.xyz/api/scanwatcher/event` (POST, JSON)
- [ ] Dashboard in **Abgehn Ops** (abgehn.xyz): Aktive Installationen, Umbenennungen gesamt, Modell-Nutzung, Version-Verteilung *(ausstehend – Server)*
- [x] Lokale Opt-out-Möglichkeit: Toggle "Anonyme Nutzungsstatistiken senden" in Einstellungen

---

## 🟡 Mittlere Priorität

### Einstellungs-Dialog verbessern
- [x] **Absender-Whitelist** editierbar: Eigene Einträge hinzufügen/entfernen (gespeichert in config.json)
- [x] **Dokumenttypen** editierbar: Eigene Begriffe → Anzeigename
- [ ] **Ordner-Profil** wechseln: mehrere Ordner-Paare (Quelle → Ziel) verwalten
- [ ] Einstellungen Export/Import als `.json`
- [ ] Verarbeitete Dateien in der App-Oberfläche anzeigen (einfache Log-Liste)

### Watcher-Konfiguration
- [ ] **Dateitypen** erweiterbar: neben `.pdf` auch `.jpg`, `.tiff`, `.png` (Bild-OCR)
- [ ] **Namensmuster** konfigurierbar: aktuell nur rein numerisch; freies Regex möglich machen
- [ ] **OCR-Seitenzahl** in Einstellungen: wie viele Seiten sollen gelesen werden (Standard: 2)
- [ ] **Stabilitäts-Timeout** in Einstellungen: wie lange auf stabile Dateigröße warten (Standard: 30s)
- [ ] Duplikat-Strategie wählbar: `_2`-Suffix / Datum anhängen / überschreiben

### UI / UX
- [ ] **Dark/Light-Mode** Umschalter (customtkinter unterstützt beides)
- [ ] **Sprache**: Englisch als zweite UI-Sprache (i18n-Vorbereitung)
- [ ] **System-Tray**: Letzten 5 umbenannten Dateien im Kontextmenü anzeigen
- [ ] **Mini-Statusfenster**: optional einblendbares kleines Fenster (immer im Vordergrund)
- [ ] Update-Check: Beim Start prüfen ob neue Version auf GitHub verfügbar (GitHub Releases API)

### Updater
- [ ] Beim Start via GitHub Releases API prüfen ob neue Version verfügbar (`GET /repos/…/releases/latest`)
- [ ] Bei verfügbarem Update: Tray-Benachrichtigung + optionaler Hinweis-Banner in der App
- [ ] **In-App-Updater**: EXE/Installer-Download im Hintergrund, dann Neustart mit neuem Installer
  - Installer-URL aus GitHub Release-Asset automatisch ermitteln
  - Download-Fortschritt anzeigen (Tray-Tooltip oder kleines Progressfenster)
  - Vor Installation: Hash-Prüfung (SHA256 aus Release-Assets)
- [ ] Update-Kanal wählbar: `stable` (default) / `beta` (GitHub Pre-Releases)
- [ ] Update-Check deaktivierbar in Einstellungen (Toggle „Automatisch auf Updates prüfen")
- [ ] Changelog der neuen Version im Benachrichtigungs-Dialog anzeigen (aus GitHub Release-Body)
- [ ] Server-seitiger „Message of the Day"-Endpoint (ops.abgehn.xyz): einmalige Meldungen schieben
  - Technischer Hinweis, kritischer Bugfix-Alert, neue Feature-Ankündigung
  - Nachricht nur einmalig zeigen (gespeicherte `last_motd_id` in config)

### Patreon-Integration
- [ ] **Opt-in Patreon-Reminder**: gelegentliche (max. 1× pro Monat) freundliche Meldung via Tray
  - Nur wenn `patreon_reminders` in config aktiviert (Standard: `true`, abschaltbar)
  - Keine Reminder wenn Nutzer bereits Patreon-Supporter ist (Supporter-Status via Token prüfbar)
- [ ] **Supporter-Token**: Patreon-Supporter können Token eingeben → schaltet Premium-Features frei und deaktiviert Reminder
  - Token-Validierung gegen ops.abgehn.xyz (einfacher Hash-Check, kein Patreon OAuth nötig)
- [ ] Reminder-Text und Intervall server-seitig steuerbar (über denselben MOTD-Endpoint)
- [ ] Patreon-Link in Tray-Kontextmenü als Menüpunkt „❤ Scan Watcher unterstützen"

---

## 🟢 Niedrige Priorität / Langfristig

### Release & Community
- [ ] **GitHub Releases** mit automatisch generiertem Changelog aus Commit-Präfixen
- [ ] **Patreon-Hinweis** im About-Dialog und im Installer-Begrüßungstext
- [ ] **About-Dialog** im Tray-Menü: Version, Lizenz (MIT), Links (GitHub, Patreon, Nova Network)
- [ ] **README.md** erweitern: Screenshots, GIF-Demo, Installations-Anleitung, Feature-Matrix
- [ ] GitHub Actions: Automatischer Build + Release bei Tag-Push

### OCR-Qualität
- [ ] **Vorverarbeitung**: Kontrast/Schärfe-Filter vor Tesseract (verbessert Erkennung bei schwachen Scans)
- [ ] Zusätzliche Tesseract-Sprachen optional nachladen
- [ ] **pdfplumber** Fallback verbessern: Tabellenstruktur für Rechnungen auswerten
- [ ] Konfidenz-Score: wenn OCR unter Schwellenwert, Datei als "PRÜFEN_" prefixen

### Sicherheit & Robustheit
- [ ] Watched-Folder Lese-/Schreibrechte beim Start prüfen, Fehler klar meldennachricht
- [ ] `UNLESBAR_`-Dateien separat in eigenem Unterordner ablegen (konfigurierbar)
- [ ] Crash-Report: Bei unbehandelten Exceptions lokale Datei + optionaler Upload zu Abgehn Ops

---

## 🔧 Technische Schulden

- [ ] Unit-Tests für `_via_ollama()` und `_via_claude()` (Mock-HTTP)
- [ ] Unit-Tests für Benennungsschema-Templates (wenn implementiert)
- [ ] `build.bat` auf `py` statt `python` umstellen (Windows-Kompatibilität)
- [ ] Installer: Tesseract optional mitbündeln oder separaten Download-Link anbieten
- [ ] `config.json` Schema-Version für Migration bei Breaking Changes

---

## 📊 Abgehn Ops – Telemetrie-Dashboard (Planung)

> Backend: Express + MySQL (bereits vorhanden in abgehn.xyz/ops)

### Neue DB-Tabelle: `scanwatcher_events`
```sql
CREATE TABLE scanwatcher_events (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  install_id   CHAR(36) NOT NULL,          -- UUID, anonym
  event        VARCHAR(32) NOT NULL,       -- install, rename, heartbeat, uninstall
  version      VARCHAR(16),
  win_build    VARCHAR(16),
  model_used   VARCHAR(32),               -- claude / ollama / rules / gpt / none
  rename_ok    TINYINT(1),
  files_total  INT,
  created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX (install_id),
  INDEX (event),
  INDEX (created_at)
);
```

### Neue Route: `POST /api/scanwatcher/event` (öffentlich, kein Auth)
- Rate-Limit: max. 10 Events/Stunde pro install_id
- Input-Validierung: event-Typ Whitelist, keine freien Strings
- Kein IP-Logging

### Dashboard-Seite `/scanwatcher` in Abgehn Ops
- Aktive Installationen (Heartbeat letzte 7 Tage)
- Umbenennungen gesamt / pro Modell (Pie-Chart)
- Versions-Verteilung (Bar-Chart)
- Tages-Aktivität (Line-Chart)
- Neue Installationen pro Woche
