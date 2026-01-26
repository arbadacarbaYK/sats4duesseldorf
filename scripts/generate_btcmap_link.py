#!/usr/bin/env python3
"""
Generate BTCMap verification link and copy-paste notes for a location.

Usage:
    python scripts/generate_btcmap_link.py <location_id> [--issue <issue_number>]
    python scripts/generate_btcmap_link.py DE-BE-00042 --issue 15

This script:
1. Looks up the OSM type and ID from locations.csv
2. Generates a BTCMap verify-location URL
3. If an issue number is provided, fetches proof URLs and generates copy-paste notes
"""

import csv
import sys
import argparse
import subprocess
import json
import re
from datetime import date
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


def get_issue_details(issue_number: int) -> dict | None:
    """Fetch issue details from GitHub using gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--json", "body,title"],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def extract_field(body: str, pattern: str) -> str:
    """Extract a field from issue body using regex."""
    match = re.search(pattern, body, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def extract_proof_urls(body: str) -> dict:
    """Extract proof URLs from issue body."""
    return {
        "public_post": extract_field(body, r"\*\*1\. Öffentlicher Post[^*]*\*\*\s*`?([^\n`]+)") or
                       extract_field(body, r"Öffentlicher Post[^\n]*\n+([^\n]+)"),
        "receipt": extract_field(body, r"\*\*2\. Kaufbeleg[^*]*\*\*\s*`?([^\n`]+)") or
                   extract_field(body, r"Kaufbeleg[^\n]*\n+([^\n]+)"),
        "payment": extract_field(body, r"\*\*3\. Bitcoin-Zahlung[^*]*\*\*\s*`?([^\n`]+)") or
                   extract_field(body, r"Bitcoin-Zahlung[^\n]*\n+([^\n]+)"),
        "venue": extract_field(body, r"\*\*4\. Foto vom Ort[^*]*\*\*\s*`?([^\n`]+)") or
                 extract_field(body, r"Foto vom Ort[^\n]*\n+([^\n]+)"),
    }


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


def generate_btcmap_notes(issue_url: str, proofs: dict) -> str:
    """Generate the copy-paste text for BTCMap notes field."""
    today = date.today().isoformat()

    lines = [
        f"Verified via sats4berlin on {today}",
        "",
        "Proof:",
        f"- Social: {proofs.get('public_post') or 'n/a'}",
        f"- Receipt: {proofs.get('receipt') or 'n/a'}",
        f"- Payment: {proofs.get('payment') or 'n/a'}",
        f"- Venue: {proofs.get('venue') or 'n/a'}",
        "",
        f"Full details: {issue_url}",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate BTCMap verification link for a location"
    )
    parser.add_argument("location_id", help="Location ID (e.g., DE-BE-00042)")
    parser.add_argument("--issue", type=int, help="GitHub issue number for context")
    parser.add_argument("--repo", default="satoshiinberlin/sats4berlin",
                       help="GitHub repo (default: satoshiinberlin/sats4berlin)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--notes-only", action="store_true", help="Only output the BTCMap notes text")

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
    proofs = {}
    btcmap_notes = ""

    if args.issue:
        github_issue_url = f"https://github.com/{args.repo}/issues/{args.issue}"

        # Fetch issue details for proof URLs
        issue_data = get_issue_details(args.issue)
        if issue_data and issue_data.get("body"):
            proofs = extract_proof_urls(issue_data["body"])
            btcmap_notes = generate_btcmap_notes(github_issue_url, proofs)

    if args.notes_only:
        if btcmap_notes:
            print(btcmap_notes)
        else:
            print("Error: --notes-only requires --issue")
            sys.exit(1)
        return

    if args.json:
        print(json.dumps({
            "location_id": args.location_id,
            "name": info["name"],
            "osm_type": osm_type,
            "osm_id": osm_id,
            "btcmap_verify_url": btcmap_url,
            "osm_url": osm_url,
            "github_issue_url": github_issue_url,
            "proofs": proofs,
            "btcmap_notes": btcmap_notes,
        }, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"  BTCMap Verification for {args.location_id}")
        print(f"{'='*60}\n")
        print(f"Location:    {info['name']}")
        print(f"OSM:         {osm_type}/{osm_id}")
        print(f"")
        print(f"BTCMap Verify URL:")
        print(f"  {btcmap_url}")
        print(f"")
        print(f"OSM URL:")
        print(f"  {osm_url}")

        if github_issue_url:
            print(f"\nGitHub Issue:")
            print(f"  {github_issue_url}")

        if btcmap_notes:
            print(f"\n{'='*60}")
            print("Copy-paste this into BTCMap 'Additional notes':")
            print(f"{'='*60}")
            print(btcmap_notes)
            print(f"{'='*60}")
        else:
            print(f"\n{'='*60}")
            print("Instructions:")
            print("1. Open the BTCMap Verify URL above")
            print("2. Fill in the verification form")
            print("3. Submit")
            print(f"{'='*60}")
        print()


if __name__ == "__main__":
    main()
