# Review-Checkliste (Maintainer)

Ein Issue kann nur **approved** werden, wenn ein Kauf vor Ort **in Bitcoin** plausibel nachgewiesen ist.

## Muss-Kriterien (sonst: needs-info oder rejected)
1) Öffentlicher Post enthält die Worte **Berlin** und **Bitcoin** und zeigt Foto/Video.
2) Bon/Beleg ist vorhanden (persönliche Daten geschwärzt).
3) Bitcoin-Zahlung ist erkennbar bestätigt ("bezahlt", Betrag/Datum).
4) Ort ist eindeutig erkennbar (Schild/Eingang/Kasse).
5) Cooldown eingehalten (letzter gültiger Check mindestens 90 Tage her).

## Einstufung
- **base**: Zahlung bestätigt, keine kritische Änderung.
- **critical_change**: nimmt kein Bitcoin mehr / geschlossen / umgezogen / wesentliche Korrektur.
- **new-location**: neuer Ort, Bounty erst nach 2 weiteren Bestätigungen.

## Labels
- Eingang: pending
- Unklar: needs-info
- Gültig: approved (+ ggf. critical-change)
- Ungültig: rejected
- Nach Auszahlung: paid

## Auszahlung
Auszahlungsziel niemals öffentlich im Issue. Nach approved wird das Ziel privat angefordert.

## Automatisierung
Nach dem Setzen des `approved`-Labels passiert automatisch:
1. Check wird in `checks_public.csv` eingetragen
2. Cooldown wird für den Ort gesetzt (90 Tage)
3. Bot kommentiert mit BTCMap-Verifikationslink (zum Kopieren)
4. Bei Web-Formular-Einreichungen: Kontaktdaten wurden bereits privat gespeichert

Bei `paid`-Label:
1. Status wird auf "paid" gesetzt
2. Aktivitätsfaktor wird neu berechnet (falls höher)
3. Budget wird aktualisiert
4. Issue wird automatisch geschlossen
