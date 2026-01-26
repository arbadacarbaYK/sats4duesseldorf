#!/usr/bin/env python3
"""
Compute cooldown eligibility for locations.

Uses the MAXIMUM of:
- source_last_update (from BTCMap/OSM check_date or survey:date)
- last_verified_at (from local sats4berlin checks)

This ensures that both BTCMap verifications AND local checks trigger cooldowns.
"""
import csv
import datetime as dt
from pathlib import Path

LOC_PATH = Path("data/locations.csv")
RAW_PATH = Path("data/berlin_raw.csv")

COOLDOWN_DAYS = 90


def parse_date(value: str):
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    # accept YYYY-MM-DD
    try:
        return dt.date.fromisoformat(s[:10])
    except (ValueError, TypeError):
        return None


def add_days(d: dt.date, days: int) -> dt.date:
    return d + dt.timedelta(days=days)


def max_date(*ds):
    out = None
    for d in ds:
        if d and (out is None or d > out):
            out = d
    return out


def main():
    if not LOC_PATH.exists():
        raise SystemExit("Missing data/locations.csv")
    if not RAW_PATH.exists():
        raise SystemExit("Missing data/berlin_raw.csv")

    # Load locations
    with LOC_PATH.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        loc_fields = r.fieldnames or []
        loc_rows = list(r)

    required_cols = [
        "source_last_update", "source_last_update_tag",
        "cooldown_until", "cooldown_days_left",
        "eligible_now", "eligible_for_check",
    ]
    for c in required_cols:
        if c not in loc_fields:
            raise SystemExit(f"Missing column in locations.csv: {c}")

    # Load raw (BTCMap/OSM extract)
    with RAW_PATH.open(newline="", encoding="utf-8") as f:
        rr = csv.DictReader(f)
        raw_fields = rr.fieldnames or []
        raw_rows = list(rr)

    for c in ["osm_type", "osm_id", "check_date", "survey:date"]:
        if c not in raw_fields:
            raise SystemExit(f"Missing column in berlin_raw.csv: {c}")

    # Index raw by (osm_type, osm_id) -> (best_date, tag_used)
    raw_index = {}
    for row in raw_rows:
        osm_type = (row.get("osm_type") or "").strip()
        osm_id = (row.get("osm_id") or "").strip()
        if not osm_type or not osm_id:
            continue

        d_check = parse_date(row.get("check_date", ""))
        d_survey = parse_date(row.get("survey:date", ""))

        # pick best date; prefer check_date if it's the newest (or only)
        d_best = max_date(d_check, d_survey)
        if not d_best:
            continue

        tag = "check_date" if (d_check and d_check == d_best) else "survey:date"
        k = (osm_type, osm_id)
        cur = raw_index.get(k)
        if cur is None or d_best > cur[0]:
            raw_index[k] = (d_best, tag)

    today = dt.date.today()

    updated = 0
    missing_upstream = 0
    used_local_check = 0

    for row in loc_rows:
        osm_type = (row.get("osm_type") or "").strip()
        osm_id = (row.get("osm_id") or "").strip()
        k = (osm_type, osm_id)

        # Get BTCMap/OSM date
        btcmap_result = raw_index.get(k)
        d_btcmap = btcmap_result[0] if btcmap_result else None
        btcmap_tag = btcmap_result[1] if btcmap_result else ""

        # Get local verification date (from sats4berlin checks)
        d_local = parse_date(row.get("last_verified_at", ""))

        # Use the MAXIMUM of both dates for cooldown calculation
        # This ensures both BTCMap and local checks trigger cooldowns
        d_effective = max_date(d_btcmap, d_local)

        # Determine which source provided the effective date
        if d_effective:
            if d_local and d_local == d_effective:
                source_tag = "local_check"
                used_local_check += 1
            else:
                source_tag = btcmap_tag
        else:
            source_tag = ""

        if not d_effective:
            # No dates at all -> allow check
            row["source_last_update"] = ""
            row["source_last_update_tag"] = ""
            row["cooldown_until"] = ""
            row["cooldown_days_left"] = "0"
            row["eligible_now"] = "yes"
            row["eligible_for_check"] = "yes"
            missing_upstream += 1
            continue

        cooldown_until = add_days(d_effective, COOLDOWN_DAYS)
        days_left = (cooldown_until - today).days
        if days_left < 0:
            days_left = 0
        eligible = "yes" if days_left == 0 else "no"

        # Update source_last_update to BTCMap date (for display/tracking)
        # But use effective date for cooldown calculation
        if d_btcmap:
            row["source_last_update"] = d_btcmap.isoformat()
            row["source_last_update_tag"] = btcmap_tag
        else:
            row["source_last_update"] = ""
            row["source_last_update_tag"] = ""

        row["cooldown_until"] = cooldown_until.isoformat()
        row["cooldown_days_left"] = str(days_left)
        row["eligible_now"] = eligible
        row["eligible_for_check"] = eligible
        updated += 1

    # Write back
    with LOC_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=loc_fields)
        w.writeheader()
        for row in loc_rows:
            w.writerow(row)

    print(f"OK: updated={updated}, missing_dates={missing_upstream}, used_local_check={used_local_check}")


if __name__ == "__main__":
    main()
