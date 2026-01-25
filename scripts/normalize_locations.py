#!/usr/bin/env python3
import csv
import datetime
from pathlib import Path

RAW = Path("data/berlin_raw.csv")
OUT = Path("data/locations.csv")

TODAY = datetime.date.today().isoformat()

# Ziel-Header (Challenge-Schema)
OUT_FIELDS = [
    "location_id","osm_type","osm_id","btcmap_url","name","category",
    "street","housenumber","postcode","city","lat","lon","website","opening_hours",
    "bitcoin_payment_status","status_note_public","last_verified_at","verified_by_count",
    "verification_confidence","bounty_base_sats","bounty_critical_sats","bounty_new_entry_sats",
    "eligible_now","last_check_id","last_updated_at",
    "source_last_update","source_last_update_tag","cooldown_until","cooldown_days_left","eligible_for_check"
]

def get(row, *keys, default=""):
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return default

def normalize_category(row):
    # je nach Export heißen Spalten z. B. category oder amenity/shop/tourism
    cat = get(row, "category", "amenity", "shop", "tourism", "office", default="")
    return cat.strip()

def normalize_bitcoin_status(row):
    # In deinem Export war das Feld oft "btc_yes" oder ähnliches.
    v = get(row, "bitcoin_payment_status", "btc_yes", "currency:BTC", "currency:XBT", "payment:bitcoin", default="").strip().lower()
    if v in ("yes","true","1"):
        return "yes"
    if v in ("no","false","0"):
        return "no"
    # wenn irgendwas gesetzt ist, aber nicht eindeutig:
    if v:
        return "unknown"
    return "unknown"

def normalize_url(row, osm_type, osm_id):
    # falls btcmap_url im raw fehlt, wenigstens OSM-Link
    url = get(row, "btcmap_url", default="").strip()
    if url:
        return url
    if osm_type and osm_id:
        return f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
    return ""

def parse_date(value: str):
    """Parse date string, return (date_str, is_valid)."""
    if not value:
        return "", False
    s = value.strip()[:10]  # Take YYYY-MM-DD part
    try:
        datetime.date.fromisoformat(s)
        return s, True
    except ValueError:
        return "", False

def get_source_last_update(row):
    """Get the most recent check/survey date and which tag it came from."""
    check_date, check_valid = parse_date(get(row, "check_date", default=""))
    survey_date, survey_valid = parse_date(get(row, "survey:date", default=""))

    if check_valid and survey_valid:
        # Return the more recent one
        if check_date >= survey_date:
            return check_date, "check_date"
        else:
            return survey_date, "survey:date"
    elif check_valid:
        return check_date, "check_date"
    elif survey_valid:
        return survey_date, "survey:date"
    else:
        return "", ""


def calculate_bounty(source_date: str) -> int:
    """
    Calculate bounty based on age since last check according to RULES.md:
    - 3-6 months: 10,000 sats
    - 6-12 months: 13,000 sats
    - 12-24 months: 17,000 sats
    - >24 months (or never checked): 21,000 sats
    """
    if not source_date:
        # Never checked = treat as >24 months
        return 21000

    try:
        last_check = datetime.date.fromisoformat(source_date[:10])
    except ValueError:
        return 21000

    today = datetime.date.today()
    days_since = (today - last_check).days
    months_since = days_since / 30.44  # Average days per month

    if months_since < 3:
        # Still in cooldown, but show minimum bounty
        return 10000
    elif months_since < 6:
        return 10000
    elif months_since < 12:
        return 13000
    elif months_since < 24:
        return 17000
    else:
        return 21000

def main():
    if not RAW.exists():
        raise SystemExit(f"Missing {RAW}")

    with RAW.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)

    # Sort stabil nach OSM-ID, damit location_id deterministisch bleibt
    def sort_key(r):
        t = get(r, "osm_type", "type", default="")
        i = get(r, "osm_id", "id", default="0")
        try:
            i = int(str(i))
        except:
            i = 0
        return (t, i)

    raw_rows.sort(key=sort_key)

    out_rows = []
    for idx, r in enumerate(raw_rows, start=1):
        osm_type = get(r, "osm_type", "type", default="").strip()
        osm_id   = str(get(r, "osm_id", "id", default="")).strip()

        location_id = f"DE-BE-{idx:05d}"
        source_date, source_tag = get_source_last_update(r)
        bounty = calculate_bounty(source_date)

        out_rows.append({
            "location_id": location_id,
            "osm_type": osm_type,
            "osm_id": osm_id,
            "btcmap_url": normalize_url(r, osm_type, osm_id),
            "name": get(r, "name", default="").strip(),
            "category": normalize_category(r),
            "street": get(r, "street", "addr:street", default="").strip(),
            "housenumber": get(r, "housenumber", "addr:housenumber", default="").strip(),
            "postcode": get(r, "postcode", "addr:postcode", default="").strip(),
            "city": get(r, "city", "addr:city", default="Berlin").strip() or "Berlin",
            "lat": str(get(r, "lat", "latitude", default="")).strip(),
            "lon": str(get(r, "lon", "longitude", default="")).strip(),
            "website": get(r, "website", "contact:website", default="").strip(),
            "opening_hours": get(r, "opening_hours", default="").strip(),
            "bitcoin_payment_status": normalize_bitcoin_status(r),
            "status_note_public": "",
            "last_verified_at": "",
            "verified_by_count": "0",
            "verification_confidence": "low",
            "bounty_base_sats": str(bounty),
            "bounty_critical_sats": "21000",
            "bounty_new_entry_sats": "21000",
            "eligible_now": "yes",  # initial, will be updated by cooldown script
            "last_check_id": "",
            "last_updated_at": TODAY,
            "source_last_update": source_date,
            "source_last_update_tag": source_tag,
            "cooldown_until": "",
            "cooldown_days_left": "0",
            "eligible_for_check": "yes",
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        w.writeheader()
        for r in out_rows:
            w.writerow(r)

    print(f"Wrote {OUT} with {len(out_rows)} rows.")

if __name__ == "__main__":
    main()
