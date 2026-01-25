#!/usr/bin/env python3
"""
Fetch Bitcoin-accepting locations in Berlin from OpenStreetMap via Overpass API.

Queries OSM directly for the most up-to-date check_date and survey:date values.
"""
import csv
import json
import urllib.request
import urllib.parse
from pathlib import Path

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OUTPUT_PATH = Path("data/berlin_raw.csv")

# Overpass query for Bitcoin-accepting places within Berlin's administrative boundary
# Uses area query with Berlin's OSM relation ID (62422) + 3600000000
OVERPASS_QUERY = """
[out:json][timeout:120];
area["name"="Berlin"]["boundary"="administrative"]["admin_level"="4"]->.berlin;
(
  node["currency:XBT"="yes"](area.berlin);
  way["currency:XBT"="yes"](area.berlin);
  node["payment:bitcoin"="yes"](area.berlin);
  way["payment:bitcoin"="yes"](area.berlin);
);
out center tags;
"""

# CSV columns for berlin_raw.csv
FIELDNAMES = [
    "name",
    "category_key",
    "category",
    "address",
    "addr:street",
    "addr:housenumber",
    "addr:postcode",
    "addr:city",
    "addr:suburb",
    "lat",
    "lon",
    "xbt",
    "btc",
    "onchain",
    "lightning",
    "payment:lightning_contactless",
    "opening_hours",
    "website",
    "phone",
    "survey:date",
    "check_date",
    "osm_type",
    "osm_id",
    "osm_url",
]


def fetch_from_overpass() -> list[dict]:
    """Fetch Bitcoin locations from OSM via Overpass API."""
    print(f"Fetching from Overpass API...")

    data = urllib.parse.urlencode({"data": OVERPASS_QUERY}).encode("utf-8")
    req = urllib.request.Request(
        OVERPASS_URL,
        data=data,
        headers={"User-Agent": "sats4berlin/1.0 (https://github.com/satoshiinberlin/sats4berlin)"},
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    elements = result.get("elements", [])
    print(f"Fetched {len(elements)} Bitcoin-accepting elements from OSM.")
    return elements


def extract_row(element: dict) -> dict:
    """Extract CSV row from OSM element."""
    tags = element.get("tags", {})
    osm_type = element.get("type", "")
    osm_id = str(element.get("id", ""))

    # Get coordinates (for ways, use center)
    lat = element.get("lat") or element.get("center", {}).get("lat", "")
    lon = element.get("lon") or element.get("center", {}).get("lon", "")

    # Build address string
    addr_parts = []
    if tags.get("addr:street"):
        street = tags.get("addr:street", "")
        housenumber = tags.get("addr:housenumber", "")
        addr_parts.append(f"{street} {housenumber}".strip())
    if tags.get("addr:postcode") or tags.get("addr:city"):
        addr_parts.append(f"{tags.get('addr:postcode', '')} {tags.get('addr:city', '')}".strip())
    if tags.get("addr:suburb"):
        addr_parts.append(tags.get("addr:suburb", ""))
    address = ", ".join(p for p in addr_parts if p)

    # Determine category from OSM tags
    category_key = ""
    category = "other"
    for key in ["amenity", "shop", "office", "tourism", "leisure", "craft"]:
        if key in tags:
            category_key = key
            category = tags[key]
            break

    # Payment methods
    def yn(val):
        if val in ("yes", "Yes", "true", "True", True):
            return "True"
        if val in ("no", "No", "false", "False", False):
            return "False"
        return ""

    # Get the most recent check_date (prefer check_date:currency:XBT, then check_date)
    check_date = tags.get("check_date:currency:XBT", "") or tags.get("check_date", "")

    return {
        "name": tags.get("name", ""),
        "category_key": category_key,
        "category": category,
        "address": address,
        "addr:street": tags.get("addr:street", ""),
        "addr:housenumber": tags.get("addr:housenumber", ""),
        "addr:postcode": tags.get("addr:postcode", ""),
        "addr:city": tags.get("addr:city", "Berlin"),
        "addr:suburb": tags.get("addr:suburb", ""),
        "lat": lat,
        "lon": lon,
        "xbt": yn(tags.get("currency:XBT")),
        "btc": yn(tags.get("currency:BTC")),
        "onchain": yn(tags.get("payment:onchain")),
        "lightning": yn(tags.get("payment:lightning")),
        "payment:lightning_contactless": tags.get("payment:lightning_contactless", ""),
        "opening_hours": tags.get("opening_hours", ""),
        "website": tags.get("website", ""),
        "phone": tags.get("phone", ""),
        "survey:date": tags.get("survey:date", ""),
        "check_date": check_date,
        "osm_type": osm_type,
        "osm_id": osm_id,
        "osm_url": f"https://www.openstreetmap.org/{osm_type}/{osm_id}" if osm_type and osm_id else "",
    }


def main():
    elements = fetch_from_overpass()

    # Extract rows
    rows = [extract_row(e) for e in elements]

    # Sort by name for consistent output
    rows.sort(key=lambda r: (r.get("name") or "").lower())

    # Write CSV
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
