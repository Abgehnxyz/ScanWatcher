# Patreon-Einrichtung – Nova Network

> Seite: patreon.com/NovaNetworkone

---

## 1. Bilder & Assets

| Was | Maße | Hinweis |
|-----|------|---------|
| **Profilbild** | 400 × 400 px | Logo Nova Network oder Scan Watcher Firefly-Icon |
| **Cover-Banner** | 1600 × 400 px | z. B. Screenshot der App + Slogan |
| **Tier-Bilder** (optional) | 400 × 400 px | Je ein Bild pro Stufe |

---

## 2. Seiten-Beschreibung (About)

Kurzer Text der auf der Patreon-Seite erscheint (~150 Wörter):

> Nova Network entwickelt kostenlose Windows-Tools für den Arbeitsalltag.
> Unser erstes Tool: **Scan Watcher** – überwacht deinen Scanner-Ordner,
> erkennt Dokumente per OCR und benennt sie automatisch intelligent um.
>
> Alle Tools sind und bleiben kostenlos. Mit deiner Unterstützung können
> wir weitere Features entwickeln, Server-Kosten decken und mehr
> Open-Source-Tools für Windows veröffentlichen.
>
> **Danke, dass du das möglich machst.**

---

## 3. Membership-Tiers

### Stufe 1 – Kaffee ☕ (3 €/Monat)
- Name im README / Credits der App
- Gutes Gewissen

### Stufe 2 – Supporter ⭐ (9 €/Monat)
- Alles aus Stufe 1
- **Supporter-Token** → deaktiviert Patreon-Erinnerungen in der App
- Early Access: Beta-Versionen vor Public Release
- Stimme bei Feature-Requests mit ab

### Stufe 3 – Power User 🚀 (25 €/Monat)
- Alles aus Stufe 1 & 2
- Feature-Request direkt einreichen (wird priorisiert)
- Direkter Kontakt per E-Mail für Support
- Name prominent in den Credits

---

## 4. Ziele (Milestones)

| Betrag/Monat | Ziel |
|-------------|------|
| 50 € | Server-Kosten gedeckt (ops.abgehn.xyz, Telemetrie-Dashboard) |
| 150 € | Zweites Windows-Tool in Entwicklung |
| 300 € | Scan Watcher bekommt eigene Installer-Seite + Dokumentation |
| 500 € | Vollzeit-Entwicklung an Nova Network Tools |

---

## 5. Erster Post (Willkommens-Post)

Titel: **„Scan Watcher ist live – und jetzt auch auf Patreon"**

Inhalt:
- Kurze Vorstellung (wer bist du, was ist Nova Network)
- Was ist Scan Watcher, wie funktioniert es
- Screenshot oder kurzes GIF der App
- Link zum GitHub-Repo
- Warum Patreon (Server, Zeit, weitere Tools)

---

## 6. Willkommens-Nachricht (automatisch an neue Supporter)

> Hallo und danke für deine Unterstützung! 🙌
>
> Du erhältst deinen **Supporter-Token** in den nächsten 24 Stunden
> per Patreon-Nachricht. Den Token gibst du in den Einstellungen von
> Scan Watcher ein (Einstellungen → Patreon-Unterstützung → Token).
>
> Bei Fragen einfach hier anschreiben.
> – Alexander, Nova Network

---

## 7. Auszahlung einrichten

- [ ] Bankkonto oder PayPal hinterlegen (Patreon → Einnahmen → Auszahlung)
- [ ] Steuer-Info ausfüllen (für DE: USt-IdNr. oder Kleinunternehmer-Hinweis)
- [ ] Auszahlungs-Schwellenwert festlegen (Empfehlung: 25 €)

---

## 8. Links & Integration

- [ ] GitHub-Link auf der Patreon-Seite eintragen
- [ ] Patreon-Link in `README.md` des Repos ergänzen
- [ ] Patreon-Link in Inno Setup Installer-Begrüßungstext
- [ ] URL in Scan Watcher bestätigen: `patreon.com/NovaNetworkone`

> **Hinweis:** Im Code steht aktuell `patreon.com/NovaNetwork` →
> muss auf `patreon.com/NovaNetworkone` geändert werden!

---

## 9. Supporter-Token-System (technisch)

Wenn jemand Supporter wird, schickst du ihm manuell (oder später automatisiert) einen Token.

**Aktuell:** Manuell generieren und per Patreon-Nachricht senden.

Token-Format (Vorschlag): `NNS-XXXX-XXXX-XXXX` (zufällig, in deiner DB hinterlegt).

Später: Automatisierung via Patreon Webhook → ops.abgehn.xyz generiert und versendet Token automatisch.
