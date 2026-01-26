#!/usr/bin/env python3
"""
Normalize and merge BTCMap data with existing locations.csv.

This script MERGES data instead of overwriting:
- Preserves all existing locations (including manually added ones)
- Preserves verification status, check history, and new_location_status
- Updates only BTCMap-sourced fields (name, address, coordinates, etc.)
- Adds new locations from BTCMap that don't exist yet
- Uses stable location IDs (never reassigns existing IDs)
"""
import csv
import datetime
from pathlib import Path

RAW = Path("data/berlin_raw.csv")
OUT = Path("data/locations.csv")

TODAY = datetime.date.today().isoformat()

# Output schema
OUT_FIELDS = [
    "location_id", "osm_type", "osm_id", "btcmap_url", "name", "category",
    "street", "housenumber", "postcode", "city", "lat", "lon", "website", "opening_hours",
    "last_verified_at", "verified_by_count",
    "verification_confidence", "bounty_base_sats", "bounty_critical_sats", "bounty_new_entry_sats",
    "new_location_status",  # empty=existing, pending=needs confirmations, confirmed=3+ checks
    "eligible_now", "last_check_id", "last_updated_at",
    "source_last_update", "source_last_update_tag", "cooldown_until", "cooldown_days_left", "eligible_for_check"
]

# Fields to PRESERVE from existing data (never overwrite from BTCMap)
PRESERVE_FIELDS = {
    "location_id",           # Never change IDs
    "last_verified_at",      # Manual verification tracking
    "verified_by_count",     # Manual verification tracking
    "verification_confidence",  # Manual verification tracking
    "new_location_status",   # Pending/confirmed status for new locations
    "last_check_id",         # Reference to last check issue
    "eligible_now",          # Computed by cooldown script
    "eligible_for_check",    # Computed by cooldown script
    "cooldown_until",        # Computed by cooldown script
    "cooldown_days_left",    # Computed by cooldown script
}

# Fields to UPDATE from BTCMap (external data source)
BTCMAP_FIELDS = {
    "name", "category", "street", "housenumber", "postcode", "city",
    "lat", "lon", "website", "opening_hours", "btcmap_url",
    "source_last_update", "source_last_update_tag",
}


def get(row, *keys, default=""):
    """Get first non-empty value from row for given keys."""
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return default


def normalize_category(row):
    """Normalize category from various OSM tags."""
    cat = get(row, "category", "amenity", "shop", "tourism", "office", default="")
    return cat.strip()


def validate_coordinates(lat_str, lon_str):
    """
    Validate and return coordinates.
    Returns (lat, lon) as strings if valid, ("", "") if invalid.
    Berlin bounds: lat ~52.3-52.7, lon ~13.1-13.8
    """
    try:
        if not lat_str or not lon_str:
            return "", ""
        lat = float(lat_str)
        lon = float(lon_str)
        # Basic global bounds check
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            print(f"Warning: Coordinates out of global bounds: {lat}, {lon}")
            return "", ""
        # Berlin-specific bounds check (warn but still accept)
        if not (52.3 <= lat <= 52.7 and 13.0 <= lon <= 13.8):
            print(f"Warning: Coordinates outside Berlin area: {lat}, {lon}")
        return str(lat), str(lon)
    except (ValueError, TypeError):
        return "", ""


def normalize_url(row, osm_type, osm_id):
    """Get BTCMap URL or construct OSM URL."""
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
    s = value.strip()[:10]
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
        return 21000

    try:
        last_check = datetime.date.fromisoformat(source_date[:10])
    except ValueError:
        return 21000

    today = datetime.date.today()
    days_since = (today - last_check).days
    months_since = days_since / 30.44

    if months_since < 3:
        return 10000  # In cooldown, show minimum
    elif months_since < 6:
        return 10000
    elif months_since < 12:
        return 13000
    elif months_since < 24:
        return 17000
    else:
        return 21000


def make_osm_key(osm_type, osm_id):
    """Create a unique key from OSM type and ID."""
    t = str(osm_type).strip().lower()
    i = str(osm_id).strip()
    if t and i:
        return f"{t}:{i}"
    return None


def get_max_location_id(rows):
    """Get the highest location ID number from existing rows."""
    max_num = 0
    for row in rows:
        lid = row.get("location_id", "")
        if lid.startswith("DE-BE-"):
            try:
                num = int(lid.replace("DE-BE-", ""))
                max_num = max(max_num, num)
            except ValueError:
                pass
    return max_num


def create_new_location_from_btcmap(raw_row, location_id):
    """Create a new location entry from BTCMap data."""
    osm_type = get(raw_row, "osm_type", "type", default="").strip()
    osm_id = str(get(raw_row, "osm_id", "id", default="")).strip()
    source_date, source_tag = get_source_last_update(raw_row)
    bounty = calculate_bounty(source_date)

    # Validate coordinates
    lat_raw = str(get(raw_row, "lat", "latitude", default="")).strip()
    lon_raw = str(get(raw_row, "lon", "longitude", default="")).strip()
    lat, lon = validate_coordinates(lat_raw, lon_raw)

    return {
        "location_id": location_id,
        "osm_type": osm_type,
        "osm_id": osm_id,
        "btcmap_url": normalize_url(raw_row, osm_type, osm_id),
        "name": get(raw_row, "name", default="").strip(),
        "category": normalize_category(raw_row),
        "street": get(raw_row, "street", "addr:street", default="").strip(),
        "housenumber": get(raw_row, "housenumber", "addr:housenumber", default="").strip(),
        "postcode": get(raw_row, "postcode", "addr:postcode", default="").strip(),
        "city": get(raw_row, "city", "addr:city", default="Berlin").strip() or "Berlin",
        "lat": lat,
        "lon": lon,
        "website": get(raw_row, "website", "contact:website", default="").strip(),
        "opening_hours": get(raw_row, "opening_hours", default="").strip(),
        "last_verified_at": "",
        "verified_by_count": "0",
        "verification_confidence": "low",
        "bounty_base_sats": str(bounty),
        "bounty_critical_sats": "21000",
        "bounty_new_entry_sats": "21000",
        "new_location_status": "",  # Empty for BTCMap locations (already verified externally)
        "eligible_now": "yes",
        "last_check_id": "",
        "last_updated_at": TODAY,
        "source_last_update": source_date,
        "source_last_update_tag": source_tag,
        "cooldown_until": "",
        "cooldown_days_left": "0",
        "eligible_for_check": "yes",
    }


def update_location_from_btcmap(existing_row, raw_row):
    """
    Update an existing location with BTCMap data.
    Only updates BTCMap-sourced fields, preserves manual fields.
    Returns True if any field was changed.
    """
    osm_type = get(raw_row, "osm_type", "type", default="").strip()
    osm_id = str(get(raw_row, "osm_id", "id", default="")).strip()
    source_date, source_tag = get_source_last_update(raw_row)
    bounty = calculate_bounty(source_date)

    # Validate coordinates
    lat_raw = str(get(raw_row, "lat", "latitude", default="")).strip()
    lon_raw = str(get(raw_row, "lon", "longitude", default="")).strip()
    lat, lon = validate_coordinates(lat_raw, lon_raw)

    # Build updated values for BTCMap fields
    updates = {
        "osm_type": osm_type,
        "osm_id": osm_id,
        "btcmap_url": normalize_url(raw_row, osm_type, osm_id),
        "name": get(raw_row, "name", default="").strip(),
        "category": normalize_category(raw_row),
        "street": get(raw_row, "street", "addr:street", default="").strip(),
        "housenumber": get(raw_row, "housenumber", "addr:housenumber", default="").strip(),
        "postcode": get(raw_row, "postcode", "addr:postcode", default="").strip(),
        "city": get(raw_row, "city", "addr:city", default="Berlin").strip() or "Berlin",
        "lat": lat,
        "lon": lon,
        "website": get(raw_row, "website", "contact:website", default="").strip(),
        "opening_hours": get(raw_row, "opening_hours", default="").strip(),
        "source_last_update": source_date,
        "source_last_update_tag": source_tag,
        "bounty_base_sats": str(bounty),
    }

    changed = False
    for key, new_value in updates.items():
        old_value = existing_row.get(key, "")
        if str(old_value).strip() != str(new_value).strip():
            existing_row[key] = new_value
            changed = True

    if changed:
        existing_row["last_updated_at"] = TODAY

    return changed


def main():
    if not RAW.exists():
        raise SystemExit(f"Missing {RAW}")

    # Load existing locations (if file exists)
    existing_rows = []
    if OUT.exists():
        with OUT.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing_rows = list(reader)
        print(f"Loaded {len(existing_rows)} existing locations from {OUT}")
    else:
        print(f"No existing {OUT}, starting fresh")

    # Index existing locations by OSM key for fast lookup
    existing_by_osm = {}
    existing_by_id = {}
    for row in existing_rows:
        osm_key = make_osm_key(row.get("osm_type"), row.get("osm_id"))
        if osm_key:
            existing_by_osm[osm_key] = row
        lid = row.get("location_id", "")
        if lid:
            existing_by_id[lid] = row

    # Load BTCMap raw data
    with RAW.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)
    print(f"Loaded {len(raw_rows)} locations from BTCMap ({RAW})")

    # Track statistics
    stats = {
        "updated": 0,
        "added": 0,
        "unchanged": 0,
        "preserved_manual": 0,
    }

    # Track which OSM keys we've seen from BTCMap
    btcmap_osm_keys = set()

    # Get next available location ID
    next_id_num = get_max_location_id(existing_rows) + 1

    # Process BTCMap data
    for raw_row in raw_rows:
        osm_type = get(raw_row, "osm_type", "type", default="").strip()
        osm_id = str(get(raw_row, "osm_id", "id", default="")).strip()
        osm_key = make_osm_key(osm_type, osm_id)

        if not osm_key:
            continue  # Skip entries without valid OSM ID

        btcmap_osm_keys.add(osm_key)

        if osm_key in existing_by_osm:
            # Update existing location
            existing_row = existing_by_osm[osm_key]
            if update_location_from_btcmap(existing_row, raw_row):
                stats["updated"] += 1
            else:
                stats["unchanged"] += 1
        else:
            # Add new location from BTCMap
            new_location_id = f"DE-BE-{next_id_num:05d}"
            next_id_num += 1

            new_row = create_new_location_from_btcmap(raw_row, new_location_id)
            existing_rows.append(new_row)
            existing_by_osm[osm_key] = new_row
            existing_by_id[new_location_id] = new_row
            stats["added"] += 1

    # Count manually added locations (those without OSM key or not in BTCMap)
    for row in existing_rows:
        osm_key = make_osm_key(row.get("osm_type"), row.get("osm_id"))
        if not osm_key or osm_key not in btcmap_osm_keys:
            # This is a manually added location or removed from BTCMap
            # We preserve it (don't delete)
            if row.get("new_location_status"):  # Has manual status = manually added
                stats["preserved_manual"] += 1

    # Sort by location_id for consistent output
    def sort_key(r):
        lid = r.get("location_id", "")
        if lid.startswith("DE-BE-"):
            try:
                return (0, int(lid.replace("DE-BE-", "")))
            except ValueError:
                pass
        return (1, lid)

    existing_rows.sort(key=sort_key)

    # Ensure all rows have all fields
    for row in existing_rows:
        for field in OUT_FIELDS:
            if field not in row:
                row[field] = ""

    # Write output
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        w.writeheader()
        for row in existing_rows:
            # Only write fields in OUT_FIELDS
            filtered_row = {k: row.get(k, "") for k in OUT_FIELDS}
            w.writerow(filtered_row)

    print(f"Wrote {OUT} with {len(existing_rows)} rows.")
    print(f"  Updated from BTCMap: {stats['updated']}")
    print(f"  Added from BTCMap: {stats['added']}")
    print(f"  Unchanged: {stats['unchanged']}")
    print(f"  Preserved manual locations: {stats['preserved_manual']}")


if __name__ == "__main__":
    main()
