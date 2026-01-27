#!/usr/bin/env python3
"""
Calculate the exact payout amount for a sats4berlin check.

Usage:
    python scripts/calculate_payout.py <issue_number>
    python scripts/calculate_payout.py 42

Requirements:
    - GitHub CLI (gh) installed and authenticated
    - Run from the repository root
"""

import subprocess
import json
import csv
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path


def get_issue(issue_number: int) -> dict:
    """Fetch issue details from GitHub."""
    result = subprocess.run(
        ["gh", "issue", "view", str(issue_number), "--json", "body,title,labels"],
        capture_output=True,
        text=True,
        check=True
    )
    return json.loads(result.stdout)


def extract_location_id(body: str) -> str | None:
    """Extract Location-ID from issue body."""
    # Try form format first: **Location-ID:** `DE-BE-00042`
    match = re.search(r"\*\*Location-ID:\*\*\s*`([^`]+)`", body)
    if match:
        return match.group(1)

    # Try GitHub issue form format
    match = re.search(r"### Location-ID\s+([A-Z]{2}-[A-Z]{2}-\d+)", body)
    if match:
        return match.group(1)

    return None


def extract_submitter_id(body: str) -> str | None:
    """Extract Submitter ID from issue body."""
    # Try new format "Submitter Ref" first (issues now show pseudonym as "Submitter")
    match = re.search(r"\*\*Submitter Ref:\*\*\s*`(USER-[A-F0-9]+)`", body)
    if match:
        return match.group(1)
    # Fall back to old format for backwards compatibility
    match = re.search(r"\*\*Submitter ID:\*\*\s*`(USER-[A-F0-9]+)`", body)
    if match:
        return match.group(1)
    return None


def extract_pseudonym(body: str) -> str | None:
    """Extract submitter pseudonym from issue body."""
    match = re.search(r"\*\*Submitter:\*\*\s*([^\n]+)", body)
    if match:
        return match.group(1).strip()
    return None


def extract_check_type(body: str) -> str:
    """Extract check type (normal or critical)."""
    if "Kritische Änderung" in body or "critical" in body.lower():
        return "critical"
    return "normal"


def is_new_location(labels: list) -> bool:
    """Check if this is a new location submission."""
    return any(label.get("name") == "new-location" for label in labels)


def get_base_bounty(location_id: str, check_type: str) -> tuple[int, str]:
    """Look up base bounty from locations.csv."""
    csv_path = Path("data/locations.csv")

    if not csv_path.exists():
        return 0, "locations.csv not found"

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("location_id") == location_id:
                if check_type == "critical":
                    return 21000, "Critical change (fixed)"

                bounty = int(row.get("bounty_base_sats", 0) or 0)
                last_check = row.get("last_verified_at", "")
                return bounty, f"Based on last check: {last_check or 'never'}"

    return 0, f"Location {location_id} not found in CSV"


def count_recent_checks(submitter_id: str, days: int = 90) -> int:
    """Count submitter's checks in the last N days."""
    if not submitter_id:
        return 0

    csv_path = Path("data/checks_public.csv")

    if not csv_path.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=days)
    count = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("submitter_id") == submitter_id:
                check_date_str = row.get("check_date", "")
                if check_date_str:
                    try:
                        check_date = datetime.fromisoformat(check_date_str.replace("Z", "+00:00"))
                        if check_date.replace(tzinfo=None) >= cutoff:
                            count += 1
                    except ValueError:
                        pass

    return count


def get_activity_multiplier(check_count: int) -> tuple[float, str]:
    """Calculate activity multiplier based on recent checks."""
    if check_count >= 10:
        return 2.0, f"2.0x ({check_count} checks in 90 days, ≥10)"
    elif check_count >= 5:
        return 1.5, f"1.5x ({check_count} checks in 90 days, 5-9)"
    elif check_count >= 2:
        return 1.2, f"1.2x ({check_count} checks in 90 days, 2-4)"
    else:
        return 1.0, f"1.0x ({check_count} checks in 90 days, 0-1)"


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/calculate_payout.py <issue_number>")
        print("Example: python scripts/calculate_payout.py 42")
        sys.exit(1)

    try:
        issue_number = int(sys.argv[1])
    except ValueError:
        print(f"Error: '{sys.argv[1]}' is not a valid issue number")
        sys.exit(1)

    print(f"\n{'='*50}")
    print(f"  PAYOUT CALCULATION FOR ISSUE #{issue_number}")
    print(f"{'='*50}\n")

    # Fetch issue
    try:
        issue = get_issue(issue_number)
    except subprocess.CalledProcessError as e:
        print(f"Error fetching issue: {e.stderr}")
        sys.exit(1)

    body = issue.get("body", "")
    labels = issue.get("labels", [])

    # Extract data
    location_id = extract_location_id(body)
    submitter_id = extract_submitter_id(body)
    pseudonym = extract_pseudonym(body)
    check_type = extract_check_type(body)
    new_location = is_new_location(labels)

    print(f"Location ID:   {location_id or 'Not found'}")
    print(f"Submitter:     {pseudonym or 'Anonymous'}")
    print(f"Submitter Ref: {submitter_id or 'Not found (GitHub submission)'}")
    print(f"Check Type:    {check_type}")
    print(f"New Location:  {'Yes' if new_location else 'No'}")
    print()

    # Calculate base bounty
    if new_location:
        base_bounty = 21000
        bounty_reason = "New location (fixed, pending 2 confirmations)"
    elif location_id:
        base_bounty, bounty_reason = get_base_bounty(location_id, check_type)
    else:
        base_bounty = 0
        bounty_reason = "Could not determine location"

    print(f"Base Bounty:   {base_bounty:,} sats")
    print(f"               {bounty_reason}")
    print()

    # Calculate multiplier
    recent_checks = count_recent_checks(submitter_id)
    multiplier, multiplier_reason = get_activity_multiplier(recent_checks)

    print(f"Multiplier:    {multiplier_reason}")
    print()

    # Final calculation
    final_payout = int(base_bounty * multiplier)

    print(f"{'='*50}")
    print(f"  FINAL PAYOUT: {final_payout:,} sats")
    print(f"  ({base_bounty:,} x {multiplier})")
    print(f"{'='*50}")

    if new_location:
        print("\n⚠️  NOTE: New location - payout held until 2 more confirmations")

    if not submitter_id:
        print("\n⚠️  NOTE: No Submitter Ref found - this was likely submitted via")
        print("   GitHub directly. Contact info must be requested manually.")

    print()


if __name__ == "__main__":
    main()
