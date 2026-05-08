# Abgehn Ops – Scan Watcher Integration

> Implementierung im Abgehn Ops Projekt (Express + MySQL)
> Ziel: Neues Menü „Scan Watcher" mit Telemetrie-Dashboard + zwei API-Endpoints

---

## 1. Datenbank

### Neue Tabelle: `scanwatcher_events`

```sql
CREATE TABLE scanwatcher_events (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  install_id   CHAR(36)     NOT NULL,
  event        VARCHAR(32)  NOT NULL,
  version      VARCHAR(16)  DEFAULT NULL,
  win_build    VARCHAR(16)  DEFAULT NULL,
  model_used   VARCHAR(32)  DEFAULT NULL,
  rename_ok    TINYINT(1)   DEFAULT NULL,
  files_total  INT          DEFAULT NULL,
  created_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_install  (install_id),
  INDEX idx_event    (event),
  INDEX idx_created  (created_at)
);
```

### Neue Tabelle: `scanwatcher_motd`

```sql
CREATE TABLE scanwatcher_motd (
  id         VARCHAR(64)   PRIMARY KEY,
  message    VARCHAR(500)  NOT NULL,
  active     TINYINT(1)    DEFAULT 1,
  created_at TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
);
```

---

## 2. API-Endpoints

### `POST /api/scanwatcher/event`
**Öffentlich, kein Auth.**

Empfängt Telemetrie-Events vom Scan Watcher Client.

**Request Body (JSON):**
```json
{
  "install_id": "uuid-v4",
  "event":      "install | rename | heartbeat",
  "version":    "1.0.9",
  "win_build":  "22000",
  "model_used": "claude | openai | gemini | mistral | groq | ollama | rules | none",
  "rename_ok":  true,
  "files_total": 42
}
```

**Validierung:**
- `event` muss einer von: `install`, `rename`, `heartbeat`, `uninstall`
- `install_id` muss UUID-Format (36 Zeichen mit Bindestrichen)
- Rate-Limit: max. **10 Events pro Stunde pro install_id**
- Kein IP-Logging
- Unbekannte Felder ignorieren

**Response:**
```json
{ "ok": true }
```
Fehler: `400` bei Validierungsfehler, `429` bei Rate-Limit.

---

### `GET /api/scanwatcher/motd`
**Öffentlich, kein Auth.**

Liefert die aktuell aktive MOTD-Nachricht (Message of the Day).  
Scan Watcher zeigt sie einmalig als Tray-Notification und speichert die `id` lokal.

**Response wenn aktive MOTD vorhanden:**
```json
{
  "id":      "2026-05-hotfix-alert",
  "message": "Wichtiger Hinweis: Bitte auf v1.1.0 updaten."
}
```

**Response wenn keine aktive MOTD:**
```json
{ "id": "", "message": "" }
```

Logik: `SELECT id, message FROM scanwatcher_motd WHERE active = 1 ORDER BY created_at DESC LIMIT 1`

---

## 3. Express Router

Neue Datei: `routes/scanwatcher.js`

```javascript
const express = require('express');
const router = express.Router();
const db = require('../db'); // bestehende DB-Verbindung

const VALID_EVENTS = ['install', 'rename', 'heartbeat', 'uninstall'];
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Einfacher In-Memory Rate-Limiter (install_id → Zeitstempel-Array)
const rateLimitMap = new Map();
function checkRateLimit(installId) {
  const now = Date.now();
  const window = 60 * 60 * 1000; // 1 Stunde
  const limit = 10;
  const timestamps = (rateLimitMap.get(installId) || []).filter(t => now - t < window);
  if (timestamps.length >= limit) return false;
  timestamps.push(now);
  rateLimitMap.set(installId, timestamps);
  return true;
}

// POST /api/scanwatcher/event
router.post('/event', async (req, res) => {
  const { install_id, event, version, win_build, model_used, rename_ok, files_total } = req.body;

  if (!install_id || !UUID_RE.test(install_id))
    return res.status(400).json({ error: 'invalid install_id' });
  if (!VALID_EVENTS.includes(event))
    return res.status(400).json({ error: 'invalid event' });
  if (!checkRateLimit(install_id))
    return res.status(429).json({ error: 'rate limit exceeded' });

  await db.query(
    `INSERT INTO scanwatcher_events
     (install_id, event, version, win_build, model_used, rename_ok, files_total)
     VALUES (?, ?, ?, ?, ?, ?, ?)`,
    [install_id, event, version || null, win_build || null,
     model_used || null, rename_ok != null ? (rename_ok ? 1 : 0) : null,
     files_total || null]
  );

  res.json({ ok: true });
});

// GET /api/scanwatcher/motd
router.get('/motd', async (req, res) => {
  const [rows] = await db.query(
    'SELECT id, message FROM scanwatcher_motd WHERE active = 1 ORDER BY created_at DESC LIMIT 1'
  );
  if (rows.length > 0) {
    res.json({ id: rows[0].id, message: rows[0].message });
  } else {
    res.json({ id: '', message: '' });
  }
});

module.exports = router;
```

**In `app.js` / `server.js` einbinden:**
```javascript
const scanwatcherRouter = require('./routes/scanwatcher');
app.use('/api/scanwatcher', scanwatcherRouter);
```

---

## 4. Dashboard-Seite

Neue Route/View: `/scanwatcher`  
Nur für eingeloggte Admins zugänglich (bestehende Auth-Middleware verwenden).

### Queries für die Charts

**Aktive Installationen** (Heartbeat letzte 7 Tage):
```sql
SELECT COUNT(DISTINCT install_id) AS active
FROM scanwatcher_events
WHERE event = 'heartbeat' AND created_at >= NOW() - INTERVAL 7 DAY;
```

**Umbenennungen gesamt:**
```sql
SELECT COUNT(*) AS total, SUM(rename_ok) AS success
FROM scanwatcher_events
WHERE event = 'rename';
```

**Modell-Nutzung** (Pie-Chart):
```sql
SELECT model_used, COUNT(*) AS cnt
FROM scanwatcher_events
WHERE event = 'rename' AND model_used IS NOT NULL
GROUP BY model_used
ORDER BY cnt DESC;
```

**Versions-Verteilung** (Bar-Chart):
```sql
SELECT version, COUNT(DISTINCT install_id) AS installs
FROM scanwatcher_events
WHERE event IN ('install', 'heartbeat') AND version IS NOT NULL
GROUP BY version
ORDER BY version DESC;
```

**Tages-Aktivität letzte 14 Tage** (Line-Chart):
```sql
SELECT DATE(created_at) AS day, COUNT(*) AS events
FROM scanwatcher_events
WHERE created_at >= NOW() - INTERVAL 14 DAY
GROUP BY DATE(created_at)
ORDER BY day;
```

**Neue Installationen pro Woche:**
```sql
SELECT YEARWEEK(created_at) AS week, COUNT(DISTINCT install_id) AS new_installs
FROM scanwatcher_events
WHERE event = 'install'
GROUP BY YEARWEEK(created_at)
ORDER BY week DESC
LIMIT 8;
```

### Dashboard-Layout (Vorschlag)

```
┌─────────────────────────────────────────────────┐
│  Scan Watcher – Monitoring                       │
├──────────┬──────────┬──────────┬────────────────┤
│ Aktive   │ Umben.   │ Erfolgs- │ Installationen │
│ Inst. 7d │ gesamt   │ rate     │ gesamt         │
├──────────┴──────────┴──────────┴────────────────┤
│  Tages-Aktivität (Line-Chart, 14 Tage)          │
├─────────────────────┬───────────────────────────┤
│  Modell-Nutzung     │  Versions-Verteilung      │
│  (Pie-Chart)        │  (Bar-Chart)              │
├─────────────────────┴───────────────────────────┤
│  MOTD verwalten: aktuelle Nachricht + Formular  │
└─────────────────────────────────────────────────┘
```

---

## 5. MOTD verwalten (Admin-UI)

Im Dashboard unten: Formular um MOTD zu setzen/deaktivieren.

```sql
-- Neue MOTD setzen (alle anderen deaktivieren):
UPDATE scanwatcher_motd SET active = 0;
INSERT INTO scanwatcher_motd (id, message, active)
VALUES ('2026-05-meine-nachricht', 'Text der Nachricht', 1);

-- MOTD deaktivieren:
UPDATE scanwatcher_motd SET active = 0;
```

---

## 6. Checkliste

- [ ] SQL: Tabellen `scanwatcher_events` und `scanwatcher_motd` anlegen
- [ ] `routes/scanwatcher.js` erstellen
- [ ] Router in `app.js` einbinden
- [ ] Dashboard-Route + View erstellen (`/scanwatcher`)
- [ ] Dashboard nur für Auth zugänglich machen (bestehende Middleware)
- [ ] Charts einbinden (Chart.js oder was bereits im Projekt vorhanden ist)
- [ ] MOTD-Verwaltungs-Formular im Dashboard
- [ ] Testen: `curl -X POST https://ops.abgehn.xyz/api/scanwatcher/event -H "Content-Type: application/json" -d '{"install_id":"00000000-0000-0000-0000-000000000001","event":"install","version":"1.0.9"}'`
- [ ] Testen: `curl https://ops.abgehn.xyz/api/scanwatcher/motd`

---

## 7. Kein API-Key nötig

Der `/api/scanwatcher/event` Endpoint ist bewusst **öffentlich ohne Auth** –  
der Scan Watcher Client hat keinen API-Key. Schutz erfolgt nur über Rate-Limiting.

Der `/api/scanwatcher/motd` Endpoint ist ebenfalls öffentlich (nur lesend).

Das **Dashboard** selbst unter `/scanwatcher` muss hinter der bestehenden  
Admin-Auth bleiben.
