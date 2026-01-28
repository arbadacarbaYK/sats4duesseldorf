#!/usr/bin/env python3
"""
Build data/locations.csv for Düsseldorf from data/duesseldorf_sheet.csv.

This replaces the old Berlin BTCMap seed with a simple, manual list based
on the curated Google Sheet export.
"""
import csv
from pathlib import Path
import datetime

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / "data" / "duesseldorf_sheet.csv"
OUT = ROOT / "data" / "locations.csv"

# Keep schema in sync with normalize_locations.py: OUT_FIELDS
OUT_FIELDS = [
    "location_id", "osm_type", "osm_id", "btcmap_url", "name", "category",
    "street", "housenumber", "postcode", "city", "lat", "lon", "website", "opening_hours",
    "last_verified_at", "verified_by_count",
    "verification_confidence", "bounty_base_sats", "bounty_critical_sats", "bounty_new_entry_sats",
    "new_location_status",
    "location_status",
    "eligible_now", "last_check_id", "last_updated_at",
    "source_last_update", "source_last_update_tag", "cooldown_until", "cooldown_days_left",
    "eligible_for_check",
]


def parse_address(addr: str):
    """
    Parse addresses like "Gladbacher Str. 5, 40219 Düsseldorf".
    Return (street, housenumber, postcode, city).
    """
    addr = (addr or "").strip()
    if not addr:
        return "", "", "", ""

    parts = [p.strip() for p in addr.split(",") if p.strip()]
    if len(parts) < 2:
        return "", "", "", ""

    street_part = parts[0]
    city_part = parts[1]

    # Street + housenumber: split on last space
    street_tokens = street_part.rsplit(" ", 1)
    if len(street_tokens) == 2:
        street, housenumber = street_tokens
    else:
        street, housenumber = street_part, ""

    # Postcode + city: first token is postcode, rest is city
    city_tokens = city_part.split(None, 1)
    if len(city_tokens) == 2:
        postcode, city = city_tokens
    else:
        postcode, city = "", city_part

    return street.strip(), housenumber.strip(), postcode.strip(), city.strip()


def main():
    if not SHEET.exists():
        raise SystemExit(f"Missing {SHEET}")

    today = datetime.date.today().isoformat()

    with SHEET.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    out_rows = []
    next_id = 1

    for row in rows:
        name = (row.get("Name Lokal bzw. Geschäft") or "").strip()
        addr = (row.get("Adresse") or "").strip()
        status = (row.get("Stand der Dinge (Bitte aktualisieren, wenn sich was geändert hat)") or "").strip()

        # Skip empty / "Nicht bewertet" rows
        if not name or not addr:
            continue
        if status.lower().startswith("nicht bewertet"):
            continue

        street, housenumber, postcode, city = parse_address(addr)

        location_id = f"DE-DUS-{next_id:05d}"
        next_id += 1

        # Very simple defaults – these can be refined later
        verification_confidence = "low"
        bounty_base = "10000"
        bounty_critical = "21000"
        bounty_new = "21000"

        out_row = {
            "location_id": location_id,
            "osm_type": "",
            "osm_id": "",
            "btcmap_url": "",
            "name": name,
            "category": "",
            "street": street,
            "housenumber": housenumber,
            "postcode": postcode,
            "city": city or "Düsseldorf",
            "lat": "",
            "lon": "",
            "website": "",
            "opening_hours": "",
            "last_verified_at": "",
            "verified_by_count": "0",
            "verification_confidence": verification_confidence,
            "bounty_base_sats": bounty_base,
            "bounty_critical_sats": bounty_critical,
            "bounty_new_entry_sats": bounty_new,
            "new_location_status": "pending",
            "location_status": "active",
            "eligible_now": "yes",
            "last_check_id": "",
            "last_updated_at": today,
            "source_last_update": "",
            "source_last_update_tag": "",
            "cooldown_until": "",
            "cooldown_days_left": "0",
            "eligible_for_check": "yes",
        }
        out_rows.append(out_row)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        writer.writeheader()
        for r in out_rows:
            writer.writerow(r)

    print(f"Wrote {OUT} with {len(out_rows)} Düsseldorf locations.")


if __name__ == "__main__":
    main()

