# Satoshis für Berlin – die Millionenchallenge
**Gesamtbounty: 1.000.000 sats (nur in Bitcoin auszahlbar)**  
Echte Bitcoin-Zahlungen vor Ort belegen, BTCMap aktuell halten, Sats verdienen.

## Worum geht es?
BTCMap (btcmap.org) listet Orte, an denen man mit Bitcoin bezahlen können soll. Solche Informationen ändern sich schnell. Diese Challenge sorgt dafür, dass Berliner Einträge regelmäßig durch echte Käufe vor Ort überprüft und bei Bedarf aktualisiert werden.

## Budget, Laufzeit, Pilot
- Das Programm läuft, bis insgesamt **1.000.000 sats** ausgeschüttet sind.
- Solange Budget verfügbar ist, kann ausgezahlt werden. Ist es aufgebraucht, ist die Runde beendet.
- Das Programm ist ein Pilot: Regeln und Abläufe können laufend verbessert werden. Maßgeblich ist die aktuelle Version dieses Dokuments.

## Grundlage: BTCMap
- Ausgangspunkt sind die BTCMap-Einträge für Berlin (auf OpenStreetMap-Daten basierend).
- Nach gültigen Checks werden Einträge bei Bedarf aktualisiert (BTCMap/OSM).

## Wer kann mitmachen?
Jeder. Keine Vorkenntnisse nötig.  
Bedingung: Du machst vor Ort einen echten Kauf und bezahlst in Bitcoin.

## Wann ist ein Check gültig?
Ein Bounty wird nur ausgezahlt, wenn ein nachweisbarer Kauf vor Ort in Bitcoin stattgefunden hat und die Nachweise vollständig sind.

### Erforderliche Nachweise (alle vier)
1) **Kaufbeleg** (Bon o.ä.; sensible Daten schwärzen)  
2) **Nachweis der Bitcoin-Zahlung** (Bestätigung „bezahlt“, Betrag/Datum sichtbar; persönliche Daten schwärzen)  
3) **Ort erkennbar** (Foto/Video von Schild, Eingang, Kasse o.ä.; keine Personen filmen)  
4) **Öffentlicher Beweis-Post** mit Foto/Video und den Worten **„Berlin“** und **„Bitcoin“** (Link wird eingereicht)

## Cooldown
Ein Ort kann frühestens 90 Tage nach dem letzten gültigen Check erneut mit einem Bounty geprüft werden. Der Cooldown berücksichtigt sowohl BTCMap-Verifikationen als auch lokale Checks aus dieser Challenge.

## Was wird aktualisiert?
Nach einem gültigen Check wird der Eintrag bei Bedarf angepasst, z. B.:
- Bitcoin-Zahlung möglich / nicht mehr möglich
- geänderte Öffnungszeiten/Website/Adresse
- geschlossen/umgezogen

## Auszahlung: nur in Bitcoin, anonymisiert
- Bounties sind in Satoshi festgelegt und werden nur in Bitcoin ausgezahlt.
- Auszahlung anonymisiert an eine Lightning-Adresse oder per eCash.
- Keine Klarnamen erforderlich.

# Bounty-Logik (in sats, nur Bitcoin-Auszahlung)

## 1) Basisbounty (nach Alter des letzten gültigen Checks)
Basisbounty gilt für normale Bestätigungen „Ort akzeptiert Bitcoin weiterhin“ ohne kritische Änderung.

**Basis (3–6 Monate): 10.000 sats**

Staffelung nach Alter seit dem letzten gültigen Check:
- **3–6 Monate:** 10.000 sats
- **6–12 Monate:** 13.000 sats
- **12–24 Monate:** 17.000 sats
- **>24 Monate:** 21.000 sats

## 2) Kritische Änderung
Für Änderungen, die für Nutzer entscheidend sind (z. B. nimmt kein Bitcoin mehr, geschlossen, umgezogen, wesentliche Korrektur):
- **21.000 sats** (unabhängig vom Alter)

## 3) Neueintrag
- **21.000 sats**, Auszahlung erst nach Bestätigung durch zwei weitere Bitcoiner
- Jede Bestätigung ist ein eigener gültiger Check (Kauf vor Ort in Bitcoin + Nachweise)
- Erst wenn 3 gültige Checks vorliegen (Einreicher + 2 Bestätiger), wird das Neueintrag-Bounty freigegeben

# Aktivitätsfaktor (bis 2,0×)
Die Auszahlung wird zusätzlich mit einem Aktivitätsfaktor multipliziert. Grundlage sind gültige Checks in den letzten 90 Tagen. Der Faktor wird zum Zeitpunkt der Auszahlung berechnet – wer also weitere Checks einreicht, bevor die Auszahlung erfolgt, profitiert vom höheren Faktor für alle offenen Bounties.

- **0–1 Checks:** **1,0×**
- **2–4 Checks:** **1,2×**
- **5–9 Checks:** **1,5×**
- **≥10 Checks:** **2,0×**

**Auszahlung = (Bounty nach Regeln oben) × Aktivitätsfaktor**

## Fairness- und Missbrauchsschutz
- Keine Auszahlung ohne Kauf vor Ort in Bitcoin.
- Keine alten Beweise, keine unklare Zuordnung.
- Fake-Checks werden abgelehnt, Wiederholungstäter gesperrt.
- Optional: pro Ort kurze Reservierung, damit niemand doppelt arbeitet.

## Hinweis zu Daten/Lizenzen
Die Ortsdaten basieren auf OpenStreetMap/BTCMap. © OpenStreetMap contributors (ODbL).  
Dieses Repo enthält zusätzlich Challenge-Metadaten (Checks/Verifizierungen/Bounty-Status).
