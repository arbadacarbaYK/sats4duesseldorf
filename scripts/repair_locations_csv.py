#!/usr/bin/env python3
import csv
from pathlib import Path

INP = Path("data/locations.csv")
OUT = Path("data/locations.csv")

# Wir wollen diese Spalte hinzufügen (falls noch nicht vorhanden)
NEW_COL = "osm_last_updated_at"

def main():
    if not INP.exists():
        raise SystemExit("data/locations.csv not found")

    with INP.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        raise SystemExit("locations.csv is empty")

    header = rows[0]
    data = rows[1:]

    # Wenn die Spalte schon existiert, prüfen wir nur Konsistenz
    if NEW_COL in header:
        expected = len(header)
        bad = [(i+2, len(r)) for i, r in enumerate(data) if len(r) != expected]
        if bad:
            raise SystemExit(f"Column mismatch even though '{NEW_COL}' exists. Examples: {bad[:5]}")
        print("OK: header already has osm_last_updated_at and all rows match.")
        return

    # Spalte einfügen: direkt nach status_note_public, falls vorhanden, sonst ans Ende
    try:
        insert_at = header.index("status_note_public") + 1
    except ValueError:
        insert_at = len(header)

    new_header = header[:]
    new_header.insert(insert_at, NEW_COL)

    fixed = []
    mismatches = []

    for idx, r in enumerate(data, start=2):  # echte Zeilennummern in Datei
        if len(r) == len(header):
            # Normfall: Spalte fehlt überall -> leeren Wert einfügen
            r2 = r[:]
            r2.insert(insert_at, "")
            fixed.append(r2)
        elif len(r) == len(new_header):
            # Diese Zeile hatte die Spalte bereits (oder wurde irgendwie korrekt angepasst)
            fixed.append(r)
        elif len(r) == len(header) + 1:
            # Häufigster Sonderfall: genau eine Zeile hat schon eine Extra-Spalte.
            # Wir nehmen an, dass diese Extra-Spalte genau an insert_at hingehört.
            # Wenn die Extra-Spalte am Ende hängt, schieben wir sie an die richtige Position.
            if len(r) == len(header) + 1:
                r2 = r[:]
                # Wenn NEW_COL am Ende "dranhängt": an die richtige Stelle verschieben
                extra = r2.pop()  # letzter Wert
                r2.insert(insert_at, extra)
                # Jetzt sollte es passen
                if len(r2) == len(new_header):
                    fixed.append(r2)
                else:
                    mismatches.append((idx, len(r), "could not align +1 row"))
        else:
            mismatches.append((idx, len(r), "unexpected column count"))

    if mismatches:
        raise SystemExit(
            "Still mismatched rows after repair attempt. "
            f"Examples: {mismatches[:5]}"
        )

    # Schreiben (sauber gequotet)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(new_header)
        w.writerows(fixed)

    print(f"Repaired: inserted '{NEW_COL}' at index {insert_at}. Rows: {len(fixed)}")

if __name__ == "__main__":
    main()
