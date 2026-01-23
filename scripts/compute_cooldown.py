#!/usr/bin/env python3
import csv
import datetime as dt
from pathlib import Path

LOC_PATH = Path("data/locations.csv")
RAW_PATH = Path("data/berlin_raw.csv")

COOLDOWN_DAYS = 90

# Kandidaten-Spalten in berlin_raw.csv / locations.csv
RAW_TIME_CANDIDATES = [
    "last_surveyed", "btcmap_last_surveyed", "surveyed_at",
    "updated_at", "last_updated_at",
    "osm_last_updated_at", "osm_last_modified",
    "timestamp", "osm_timestamp",
    "created_at",
]

JOIN_KEY_SETS = [
    ("osm_type", "osm_id"),
    ("osm_element_type", "osm_element_id"),
    ("element_type", "element_id"),
    ("location_id",),
]

def parse_date_any(value: str):
    """Accepts YYYY-MM-DD or ISO timestamps; returns date or None."""
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    # normalize common forms
    # 2026-01-23
    try:
        return dt.date.fromisoformat(s[:10])
    except Exception:
        pass
    # 2026-01-23T08:12:34Z / 2026-01-23 08:12:34
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except Exception:
        return None

def add_days(d: dt.date, days: int) -> dt.date:
    return d + dt.timedelta(days=days)

def pick_existing(headers, candidates):
    hs = set(headers)
    for c in candidates:
        if c in hs:
            return c
    return None

def detect_join(headers_loc, headers_raw):
    hs_loc = set(headers_loc)
    hs_raw = set(headers_raw)
    for keys in JOIN_KEY_SETS:
        if all(k in hs_loc for k in keys) and all(k in hs_raw for k in keys):
            return keys
    return None

def make_key(row, keys):
    return tuple((row.get(k) or "").strip() for k in keys)

def main():
    if not LOC_PATH.exists():
        raise SystemExit("Missing data/locations.csv")
    if not RAW_PATH.exists():
        raise SystemExit("Missing data/berlin_raw.csv")

    # load locations
    with LOC_PATH.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        loc_fields = r.fieldnames or []
        loc_rows = list(r)

    required = ["source_last_update", "cooldown_until", "cooldown_days_left", "eligible_for_check"]
    for c in required:
        if c not in loc_fields:
            raise SystemExit(f"Missing column in locations.csv: {c}")

    # load raw
    with RAW_PATH.open(newline="", encoding="utf-8") as f:
        rr = csv.DictReader(f)
        raw_fields = rr.fieldnames or []
        raw_rows = list(rr)

    join_keys = detect_join(loc_fields, raw_fields)
    if not join_keys:
        raise SystemExit(
            "Cannot find a common join key between locations.csv and berlin_raw.csv.\n"
            f"locations columns: {', '.join(loc_fields[:40])}...\n"
            f"raw columns: {', '.join(raw_fields[:40])}..."
        )

    raw_time_col = pick_existing(raw_fields, RAW_TIME_CANDIDATES)
    if not raw_time_col:
        # Not fatal: we can still try to use locations’ own value
        raw_time_col = None

    # index raw by join key -> max date
    raw_max_date = {}
    for row in raw_rows:
        k = make_key(row, join_keys)
        if not any(k):
            continue
        d = parse_date_any(row.get(raw_time_col, "")) if raw_time_col else None
        if d is None:
            # try other candidates if primary missing/empty
            for c in RAW_TIME_CANDIDATES:
                if c in row:
                    d = parse_date_any(row.get(c, ""))
                    if d:
                        break
        if not d:
            continue
        cur = raw_max_date.get(k)
        if (cur is None) or (d > cur):
            raw_max_date[k] = d

    today = dt.date.today()

    updated = 0
    for row in loc_rows:
        k = make_key(row, join_keys)

        # candidate: raw max date
        d_raw = raw_max_date.get(k)

        # candidate: existing source_last_update (if already there)
        d_existing = parse_date_any(row.get("source_last_update", ""))

        # choose newest available
        d = d_raw
        if d_existing and (not d or d_existing > d):
            d = d_existing

        if not d:
            # if we cannot determine, leave fields blank/neutral
            row["source_last_update"] = row.get("source_last_update", "") or ""
            row["cooldown_until"] = row.get("cooldown_until", "") or ""
            row["cooldown_days_left"] = row.get("cooldown_days_left", "") or ""
            row["eligible_for_check"] = row.get("eligible_for_check", "") or ""
            continue

        cooldown_until = add_days(d, COOLDOWN_DAYS)
        days_left = (cooldown_until - today).days
        eligible = "yes" if days_left <= 0 else "no"

        row["source_last_update"] = d.isoformat()
        row["cooldown_until"] = cooldown_until.isoformat()
        row["cooldown_days_left"] = str(days_left if days_left > 0 else 0)
        row["eligible_for_check"] = eligible
        updated += 1

    # write back (same column order)
    with LOC_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=loc_fields)
        w.writeheader()
        for row in loc_rows:
            w.writerow(row)

    print(f"OK: cooldown computed. join_keys={join_keys}, raw_time_col={raw_time_col}, updated_rows={updated}")

if __name__ == "__main__":
    main()
