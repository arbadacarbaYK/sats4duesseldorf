# Tally Form Specifications

Diese Dokumentation beschreibt die Tally-Formulare für sats4berlin.

## Übersicht

Es gibt zwei Formulare:
1. **Check einreichen** - Für bestehende Orte
2. **Neuen Ort melden** - Für neue Orte, die noch nicht in der Liste sind

Beide Formulare senden Daten an den Cloudflare Worker, der:
- Öffentliche Daten als GitHub Issue erstellt
- Private Kontaktdaten sicher in Cloudflare KV speichert

---

## Formular 1: Check einreichen

### Felder (in dieser Reihenfolge)

| Feld-ID | Typ | Label | Beschreibung | Pflicht |
|---------|-----|-------|--------------|---------|
| `location_id` | Text (kurz) | Location-ID | Die ID findest du auf sats4berlin.de (z.B. DE-BE-00042) | ✅ |
| `date_time` | Text (kurz) | Datum und Uhrzeit | Wann hast du bezahlt? (z.B. 25.01.2026, ca. 14:30) | ✅ |
| `check_type` | Dropdown | Art des Checks | Optionen: "Normaler Check", "Kritische Änderung" | ✅ |
| `public_post_url` | URL | Öffentlicher Post | Link zu deinem Post (muss "Berlin" und "Bitcoin" enthalten) | ✅ |
| `receipt_proof_url` | URL | Kaufbeleg | Foto vom Bon/Rechnung (persönliche Daten schwärzen!) | ✅ |
| `payment_proof_url` | URL | Bitcoin-Zahlung | Screenshot mit Bestätigung "bezahlt" | ✅ |
| `venue_photo_url` | URL | Foto vom Ort | Schild, Eingang oder Kasse | ✅ |
| `observations` | Text (lang) | Wie lief die Zahlung? | Kurze Beschreibung deiner Erfahrung | ✅ |
| `suggested_updates` | Text (lang) | Änderungen nötig? | Falls Daten aktualisiert werden müssen | ❌ |
| --- | Trennlinie | --- | --- | --- |
| `contact_method` | Dropdown | Auszahlungsmethode | Optionen: siehe unten | ✅ |
| `contact_value` | Text (kurz) | Auszahlungsadresse | Deine Adresse/npub (wird NICHT öffentlich gepostet) | ✅ |

### Check-Typ Optionen
```
- Normaler Check – Ort akzeptiert weiterhin Bitcoin
- Kritische Änderung – Ort nimmt kein Bitcoin mehr / geschlossen / umgezogen
```

### Auszahlungsmethode Optionen
```
- Lightning-Adresse (z.B. name@getalby.com)
- Cashu / eCash Token
- Nostr DM (npub eingeben)
```

### Hinweistext für private Felder
> **Deine Kontaktdaten bleiben privat!**
> Diese Informationen werden NICHT im öffentlichen GitHub Issue erscheinen.
> Sie werden nur zur Auszahlung verwendet und danach gelöscht.

---

## Formular 2: Neuen Ort melden

### Felder (in dieser Reihenfolge)

| Feld-ID | Typ | Label | Beschreibung | Pflicht |
|---------|-----|-------|--------------|---------|
| `name` | Text (kurz) | Name des Ortes | Wie heißt das Geschäft/Restaurant/etc.? | ✅ |
| `address` | Text (kurz) | Adresse | Vollständige Adresse mit PLZ (z.B. Musterstr. 1, 10115 Berlin) | ✅ |
| `category` | Dropdown | Kategorie | Was für ein Ort ist es? | ✅ |
| `website` | URL | Website | Falls vorhanden | ❌ |
| `osm_url` | URL | OpenStreetMap-Link | Falls der Ort bereits in OSM existiert | ❌ |
| --- | Trennlinie | --- | --- | --- |
| `date_time` | Text (kurz) | Datum und Uhrzeit | Wann hast du dort bezahlt? | ✅ |
| `public_post_url` | URL | Öffentlicher Post | Link zu deinem Post | ✅ |
| `receipt_proof_url` | URL | Kaufbeleg | Foto vom Bon/Rechnung | ✅ |
| `payment_proof_url` | URL | Bitcoin-Zahlung | Screenshot der Wallet | ✅ |
| `venue_photo_url` | URL | Foto vom Ort | Schild, Eingang oder Kasse | ✅ |
| `notes` | Text (lang) | Wie lief die Zahlung? | Beschreibe deine Erfahrung, nenne Öffnungszeiten falls bekannt | ✅ |
| --- | Trennlinie | --- | --- | --- |
| `contact_method` | Dropdown | Auszahlungsmethode | Wie möchtest du die Sats erhalten? | ✅ |
| `contact_value` | Text (kurz) | Auszahlungsadresse | Deine Adresse (privat) | ✅ |

### Kategorie Optionen
```
- Restaurant / Café / Bar
- Einzelhandel / Shop
- Dienstleistung
- Hotel / Unterkunft
- Sonstiges
```

---

## Tally Webhook Konfiguration

1. Gehe zu **Form Settings** → **Integrations** → **Webhooks**
2. Klicke "Add webhook"
3. Konfiguriere:
   - **URL:** `https://sats4berlin-form-handler.<subdomain>.workers.dev/webhook/tally`
   - **Method:** POST
   - **Content-Type:** application/json
4. Speichern

---

## Design-Empfehlungen

### Intro-Text für Check-Formular
```markdown
# Satoshis für Berlin – Bounty claimen

Du hast in Berlin vor Ort mit Bitcoin bezahlt? Fülle dieses Formular aus und sichere dir deinen Bounty!

**So funktioniert's:**
1. Du gibst die Location-ID ein (findest du auf sats4berlin.de)
2. Du lädst deine Nachweise hoch
3. Du gibst deine Auszahlungsadresse an (bleibt privat!)
4. Nach Prüfung erhältst du deine Sats

**Bounty-Höhe:** 10.000 - 42.000 Sats (abhängig von Alter und Aktivität)
```

### Intro-Text für Neuer-Ort-Formular
```markdown
# Satoshis für Berlin – Neuen Ort melden

Du hast einen Ort gefunden, der Bitcoin akzeptiert, aber noch nicht in unserer Liste ist?

**Bounty: 21.000 Sats** – Auszahlung erfolgt, sobald 2 weitere Bitcoiner den Ort bestätigt haben.

**Wichtig:** Du musst vor Ort einen echten Kauf mit Bitcoin getätigt haben!
```

### Hinweis vor den privaten Feldern
```markdown
---

## Auszahlung (privat)

Die folgenden Angaben werden **NICHT** öffentlich gepostet. Sie dienen nur zur Auszahlung deines Bounties.

Nach erfolgreicher Prüfung erhältst du die Sats automatisch an die angegebene Adresse.
```

### Abschluss-Text
```markdown
---

**Danke für deinen Beitrag zu Satoshis für Berlin!**

Nach dem Absenden wird automatisch ein GitHub Issue erstellt (ohne deine Kontaktdaten). Du kannst den Status dort verfolgen.
```

---

## Tally Branding

- **Primärfarbe:** #F7931A (Bitcoin Orange)
- **Logo:** sats4berlin Logo oder Bitcoin-Symbol
- **Submit-Button:** "Check einreichen" / "Ort melden"

---

## Testmodus

Vor dem Live-Schalten:
1. Worker im Dev-Modus starten: `npm run dev`
2. Tally-Webhook auf lokalen URL setzen (z.B. via ngrok)
3. Testformular ausfüllen
4. Prüfen ob GitHub Issue erstellt wurde
5. Prüfen ob KV-Eintrag vorhanden ist
