#!/usr/bin/env python3
"""
Fetch Bitcoin-accepting locations in Berlin from BTCMap.org API.

BTCMap provides a static JSON endpoint with all elements globally.
We filter by Berlin bounding box and extract relevant fields.
"""
import csv
import json
import urllib.request
from pathlib import Path

# Berlin bounding box (approximate city limits)
BERLIN_BBOX = {
    "min_lat": 52.33,
    "max_lat": 52.68,
    "min_lon": 13.07,
    "max_lon": 13.78,
}

BTCMAP_ELEMENTS_URL = "https://static.btcmap.org/api/v2/elements.json"
OUTPUT_PATH = Path("data/berlin_raw.csv")

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


def fetch_elements() -> list[dict]:
    """Fetch all elements from BTCMap API."""
    print(f"Fetching elements from {BTCMAP_ELEMENTS_URL}...")
    req = urllib.request.Request(
        BTCMAP_ELEMENTS_URL,
        headers={"User-Agent": "sats4berlin/1.0 (https://github.com/satoshiinberlin/sats4berlin)"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    print(f"Fetched {len(data)} elements globally.")
    return data


def is_in_berlin(element: dict) -> bool:
    """Check if element is within Berlin bounding box."""
    osm = element.get("osm_json", {})
    lat = osm.get("lat")
    lon = osm.get("lon")
    if lat is None or lon is None:
        return False
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    return (
        BERLIN_BBOX["min_lat"] <= lat <= BERLIN_BBOX["max_lat"]
        and BERLIN_BBOX["min_lon"] <= lon <= BERLIN_BBOX["max_lon"]
    )


def is_active(element: dict) -> bool:
    """Check if element is not deleted."""
    deleted = element.get("deleted_at", "")
    return not deleted or deleted == ""


def extract_row(element: dict) -> dict:
    """Extract CSV row from BTCMap element."""
    osm = element.get("osm_json", {})
    tags = osm.get("tags", {})
    btcmap_tags = element.get("tags", {})

    # Determine OSM type and ID from element ID (format: "node:123456")
    elem_id = element.get("id", "")
    osm_type, osm_id = "", ""
    if ":" in elem_id:
        osm_type, osm_id = elem_id.split(":", 1)

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
    category = btcmap_tags.get("category", "other")
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
        "lat": osm.get("lat", ""),
        "lon": osm.get("lon", ""),
        "xbt": yn(tags.get("currency:XBT")),
        "btc": yn(tags.get("currency:BTC")),
        "onchain": yn(tags.get("payment:onchain")),
        "lightning": yn(tags.get("payment:lightning")),
        "payment:lightning_contactless": tags.get("payment:lightning_contactless", ""),
        "opening_hours": tags.get("opening_hours", ""),
        "website": tags.get("website", ""),
        "phone": tags.get("phone", ""),
        "survey:date": tags.get("survey:date", ""),
        "check_date": tags.get("check_date", ""),
        "osm_type": osm_type,
        "osm_id": osm_id,
        "osm_url": f"https://www.openstreetmap.org/{osm_type}/{osm_id}" if osm_type and osm_id else "",
    }


def main():
    elements = fetch_elements()

    # Filter for Berlin and active elements
    berlin_elements = [e for e in elements if is_in_berlin(e) and is_active(e)]
    print(f"Found {len(berlin_elements)} active elements in Berlin.")

    # Extract rows
    rows = [extract_row(e) for e in berlin_elements]

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
