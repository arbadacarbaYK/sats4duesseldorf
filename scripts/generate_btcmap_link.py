#!/usr/bin/env python3
"""
Generate BTCMap verification link for a location.

Usage:
    python scripts/generate_btcmap_link.py <location_id> [--issue <issue_number>]
    python scripts/generate_btcmap_link.py DE-BE-00042 --issue 15

This script:
1. Looks up the OSM type and ID from locations.csv
2. Generates a BTCMap verify-location URL
3. Optionally includes the GitHub issue link for context
"""

import csv
import sys
import argparse
import urllib.parse
from pathlib import Path


def get_location_osm_info(location_id: str) -> dict | None:
    """Look up OSM info from locations.csv."""
    csv_path = Path("data/locations.csv")

    if not csv_path.exists():
        return None

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("location_id") == location_id:
                return {
                    "location_id": location_id,
                    "name": row.get("name", ""),
                    "osm_type": row.get("osm_type", ""),
                    "osm_id": row.get("osm_id", ""),
                }
    return None


def generate_btcmap_verify_url(osm_type: str, osm_id: str) -> str:
    """Generate BTCMap verification URL."""
    if not osm_type or not osm_id:
        return ""
    return f"https://btcmap.org/verify-location?id={osm_type}:{osm_id}"


def generate_osm_url(osm_type: str, osm_id: str) -> str:
    """Generate OpenStreetMap URL."""
    if not osm_type or not osm_id:
        return ""
    return f"https://www.openstreetmap.org/{osm_type}/{osm_id}"


def main():
    parser = argparse.ArgumentParser(
        description="Generate BTCMap verification link for a location"
    )
    parser.add_argument("location_id", help="Location ID (e.g., DE-BE-00042)")
    parser.add_argument("--issue", type=int, help="GitHub issue number for context")
    parser.add_argument("--repo", default="satoshiinberlin/sats4berlin",
                       help="GitHub repo (default: satoshiinberlin/sats4berlin)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Look up location
    info = get_location_osm_info(args.location_id)

    if not info:
        print(f"Error: Location {args.location_id} not found in locations.csv")
        sys.exit(1)

    osm_type = info["osm_type"]
    osm_id = info["osm_id"]

    if not osm_type or not osm_id:
        print(f"Error: Location {args.location_id} has no OSM data")
        print("This location needs to be added to OpenStreetMap first.")
        sys.exit(1)

    btcmap_url = generate_btcmap_verify_url(osm_type, osm_id)
    osm_url = generate_osm_url(osm_type, osm_id)

    github_issue_url = ""
    if args.issue:
        github_issue_url = f"https://github.com/{args.repo}/issues/{args.issue}"

    if args.json:
        import json
        print(json.dumps({
            "location_id": args.location_id,
            "name": info["name"],
            "osm_type": osm_type,
            "osm_id": osm_id,
            "btcmap_verify_url": btcmap_url,
            "osm_url": osm_url,
            "github_issue_url": github_issue_url,
        }, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"  BTCMap Verification for {args.location_id}")
        print(f"{'='*60}\n")
        print(f"Location:    {info['name']}")
        print(f"OSM:         {osm_type}/{osm_id}")
        print(f"OSM URL:     {osm_url}")
        print(f"")
        print(f"BTCMap Verify URL:")
        print(f"  {btcmap_url}")

        if github_issue_url:
            print(f"\nGitHub Issue (for context):")
            print(f"  {github_issue_url}")

        print(f"\n{'='*60}")
        print("Instructions:")
        print("1. Click the BTCMap Verify URL above")
        print("2. Fill in the verification form")
        print("3. In 'Additional notes', paste the GitHub issue link")
        print("4. Submit the form")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
