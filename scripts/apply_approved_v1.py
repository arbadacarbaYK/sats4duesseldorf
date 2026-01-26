#!/usr/bin/env python3
import json
import re
import csv
import datetime
import urllib.request
import urllib.error
from pathlib import Path

LOCATIONS = Path("data/locations.csv")
CHECKS = Path("data/checks_public.csv")
APPROVED_ISSUES = Path("data/_approved_issues.json")

def today_iso() -> str:
    return datetime.date.today().isoformat()

def validate_url(url: str, timeout: int = 10) -> tuple[bool, str]:
    """
    Check if a URL is reachable.
    Returns (is_valid, error_message).
    """
    if not url or not url.startswith(("http://", "https://")):
        return False, "Invalid or missing URL"

    try:
        req = urllib.request.Request(url, method="HEAD", headers={
            "User-Agent": "sats4berlin-validator/1.0"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status < 400:
                return True, ""
            return False, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        # Some servers don't support HEAD, try GET
        if e.code == 405:
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "sats4berlin-validator/1.0"
                })
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return True, ""
            except Exception as e2:
                return False, str(e2)
        return False, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, str(e.reason)
    except Exception as e:
        return False, str(e)

def validate_proof_urls(public_post: str, receipt: str, payment: str, venue: str) -> list[str]:
    """
    Validate all proof URLs and return list of warnings.
    """
    warnings = []
    urls = [
        ("Public post", public_post),
        ("Receipt proof", receipt),
        ("Payment proof", payment),
        ("Venue photo", venue),
    ]

    for name, url in urls:
        if not url:
            warnings.append(f"{name}: missing")
        else:
            valid, error = validate_url(url)
            if not valid:
                warnings.append(f"{name}: {error} ({url[:50]}...)")

    return warnings

def days_ago(days: int) -> str:
    """Return ISO date string for N days ago."""
    return (datetime.date.today() - datetime.timedelta(days=days)).isoformat()

def calculate_activity_factor(submitter_id: str, existing_checks: list) -> tuple[float, int]:
    """
    Calculate activity factor based on submitter's approved checks in last 90 days.
    Returns (factor, check_count).

    Per RULES.md:
    - 0-1 checks: 1.0×
    - 2-4 checks: 1.2×
    - 5-9 checks: 1.5×
    - ≥10 checks: 2.0×
    """
    cutoff = days_ago(90)
    count = 0
    for chk in existing_checks:
        if (chk.get("submitter_id", "") == submitter_id and
            chk.get("review_status") == "approved" and
            chk.get("reviewed_at", "") >= cutoff):
            count += 1

    if count >= 10:
        return 2.0, count
    elif count >= 5:
        return 1.5, count
    elif count >= 2:
        return 1.2, count
    else:
        return 1.0, count

def add_days(date_iso: str, days: int) -> str:
    d = datetime.date.fromisoformat(date_iso)
    return (d + datetime.timedelta(days=days)).isoformat()

def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r), r.fieldnames

def write_csv(path: Path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)

def body_field(body: str, label: str) -> str:
    """
    GitHub Issue Forms render fields roughly as:
      Label
      value
    We grab the first non-empty line after the label.
    """
    m = re.search(rf"{re.escape(label)}\s*\n+([^\n]+)", body or "", re.IGNORECASE)
    return (m.group(1).strip() if m else "")

def generate_new_location_id(loc_rows: list) -> str:
    """Generate next available location ID with uniqueness check."""
    existing_ids = set()
    max_num = 0
    for r in loc_rows:
        lid = r.get("location_id", "")
        if lid.startswith("DE-BE-"):
            existing_ids.add(lid)
            try:
                num = int(lid.replace("DE-BE-", ""))
                max_num = max(max_num, num)
            except ValueError:
                print(f"Warning: Invalid location ID format: {lid}")

    # Generate new ID and verify it doesn't exist
    new_id = f"DE-BE-{max_num + 1:05d}"
    attempts = 0
    while new_id in existing_ids and attempts < 1000:
        max_num += 1
        new_id = f"DE-BE-{max_num + 1:05d}"
        attempts += 1

    if attempts >= 1000:
        raise RuntimeError("Could not generate unique location ID after 1000 attempts")

    return new_id


def main():
    if not APPROVED_ISSUES.exists():
        print("No approved issues payload found.")
        return

    issues = json.loads(APPROVED_ISSUES.read_text(encoding="utf-8"))
    if not isinstance(issues, list):
        print("Unexpected issues JSON shape (expected list).")
        return

    loc_rows, loc_fields = read_csv(LOCATIONS)
    chk_rows, chk_fields = read_csv(CHECKS)

    # Ensure new_location_status field exists
    if "new_location_status" not in loc_fields:
        # Insert after bounty_new_entry_sats
        idx = loc_fields.index("bounty_new_entry_sats") + 1 if "bounty_new_entry_sats" in loc_fields else len(loc_fields)
        loc_fields.insert(idx, "new_location_status")
        for r in loc_rows:
            r["new_location_status"] = r.get("new_location_status", "")

    loc_by_id = {r["location_id"]: r for r in loc_rows}
    existing = {r["check_id"] for r in chk_rows if r.get("check_id")}

    appended = 0
    new_locations_added = 0

    for it in issues:
        number = it.get("number")
        if number is None:
            continue

        body = it.get("body") or ""

        # labels from GitHub API are objects with {name: "..."}
        labels = set()
        for l in it.get("labels", []):
            if isinstance(l, dict) and "name" in l:
                labels.add(l["name"])

        # Check if this is a new-location issue
        is_new_location = "new-location" in labels

        # Extract location_id (for existing locations) or generate new one
        location_id = (
            body_field(body, "Location-ID (aus locations.csv)")
            or body_field(body, "Location-ID")
        )

        if is_new_location and not location_id:
            # New location: generate ID and create entry
            location_id = generate_new_location_id(loc_rows)
            name = body_field(body, "Name des Ortes") or ""
            address = body_field(body, "Adresse") or ""
            latlon = body_field(body, "Koordinaten (optional, hilft sehr)") or ""
            osm_url = (
                body_field(body, "OpenStreetMap-Link (optional)") or
                body_field(body, "OSM-Link (optional, falls vorhanden)") or
                ""
            )
            website = body_field(body, "Website (optional)") or ""
            category_raw = body_field(body, "Kategorie") or ""

            # Map category to simple form
            category = ""
            if "restaurant" in category_raw.lower() or "café" in category_raw.lower() or "bar" in category_raw.lower():
                category = "restaurant"
            elif "einzelhandel" in category_raw.lower() or "shop" in category_raw.lower():
                category = "shop"
            elif "dienstleistung" in category_raw.lower():
                category = "service"
            elif "hotel" in category_raw.lower() or "unterkunft" in category_raw.lower():
                category = "hotel"
            else:
                category = "other"

            # Parse lat/lon
            lat, lon = "", ""
            if latlon:
                parts = latlon.replace(" ", "").split(",")
                if len(parts) == 2:
                    lat, lon = parts[0], parts[1]

            # Parse OSM type/id from URL
            osm_type, osm_id = "", ""
            if osm_url:
                m = re.search(r"openstreetmap\.org/(node|way|relation)/(\d+)", osm_url)
                if m:
                    osm_type, osm_id = m.group(1), m.group(2)

            # Parse address parts
            street, housenumber, postcode = "", "", ""
            addr_parts = address.split(",")
            if len(addr_parts) >= 1:
                street_part = addr_parts[0].strip()
                # Try to split street and housenumber
                m = re.match(r"(.+?)\s+(\d+\S*)$", street_part)
                if m:
                    street, housenumber = m.group(1), m.group(2)
                else:
                    street = street_part
            if len(addr_parts) >= 2:
                plz_city = addr_parts[1].strip()
                m = re.match(r"(\d{5})\s*", plz_city)
                if m:
                    postcode = m.group(1)

            new_loc = {
                "location_id": location_id,
                "osm_type": osm_type,
                "osm_id": osm_id,
                "btcmap_url": osm_url,
                "name": name,
                "category": category,
                "street": street,
                "housenumber": housenumber,
                "postcode": postcode,
                "city": "Berlin",
                "lat": lat,
                "lon": lon,
                "website": website,
                "opening_hours": "",
                "last_verified_at": today_iso(),
                "verified_by_count": "1",
                "verification_confidence": "low",
                "bounty_base_sats": "21000",
                "bounty_critical_sats": "21000",
                "bounty_new_entry_sats": "21000",
                "new_location_status": "pending",  # Needs 2 more confirmations
                "eligible_now": "yes",
                "last_check_id": "",
                "last_updated_at": today_iso(),
                "source_last_update": "",
                "source_last_update_tag": "",
                "cooldown_until": "",
                "cooldown_days_left": "0",
                "eligible_for_check": "yes",
            }
            loc_rows.append(new_loc)
            loc_by_id[location_id] = new_loc
            new_locations_added += 1
            print(f"Created new location: {location_id} - {name}")

        if not location_id:
            continue

        # Deterministic check id from issue number (no duplicates)
        check_id = f"ISSUE-{number}"
        if check_id in existing:
            continue

        # Get submitter ID - prefer form-generated ID, fall back to GitHub username
        submitter_id = ""
        # Try to extract Submitter ID from form submission (USER-XXXX format)
        submitter_match = re.search(r"\*\*Submitter ID:\*\*\s*`(USER-[A-F0-9]+)`", body or "")
        if submitter_match:
            submitter_id = submitter_match.group(1)
        else:
            # Fall back to GitHub username for direct GitHub submissions
            user_obj = it.get("user")
            if isinstance(user_obj, dict):
                submitter_id = user_obj.get("login", "")

        # Determine check type (handle both old and new format)
        check_type_raw = (
            body_field(body, "Art des Checks") or
            body_field(body, "Check-Typ") or
            ""
        ).strip().lower()

        # Map to normalized type
        if "kritisch" in check_type_raw or "critical" in check_type_raw or check_type_raw == "critical_change":
            check_type = "critical_change"
        elif "normal" in check_type_raw or check_type_raw == "base":
            check_type = "base"
        elif "critical-change" in labels:
            check_type = "critical_change"
        else:
            check_type = "base"

        # Get bounty from locations.csv (age-based) or use critical change amount
        if check_type == "critical_change":
            base_bounty = 21000
        else:
            lr = loc_by_id.get(location_id)
            if lr:
                try:
                    base_bounty = int(lr.get("bounty_base_sats", "10000") or "10000")
                except ValueError:
                    base_bounty = 10000
            else:
                base_bounty = 10000

        # Calculate activity factor based on submitter's recent checks
        activity_factor, recent_count = calculate_activity_factor(submitter_id, chk_rows)
        final_bounty = int(base_bounty * activity_factor)

        # Extract URLs
        public_post_url = (
            body_field(body, 'Öffentlicher Beweis-Post (muss "Berlin" und "Bitcoin" enthalten)')
            or body_field(body, "Öffentlicher Beweis-Post")
        )
        receipt_proof_url = (
            body_field(body, "Beleg (Bon) – Link (Daten schwärzen)")
            or body_field(body, "Beleg (Bon)")
        )
        payment_proof_url = (
            body_field(body, 'Bitcoin-Zahlungsnachweis – Link (Bestätigung "bezahlt", Betrag/Datum sichtbar; Daten schwärzen)')
            or body_field(body, "Bitcoin-Zahlungsnachweis")
        )
        venue_photo_url = (
            body_field(body, "Ort erkennbar – Foto/Video-Link (Schild/Eingang/Kasse)")
            or body_field(body, "Ort erkennbar")
        )

        submitted_at = body_field(body, "Datum/Uhrzeit des Kaufs") or ""
        observations = body_field(body, "Beobachtungen (kurz)") or body_field(body, "Hinweise (kurz)") or ""

        # Validate proof URLs
        url_warnings = validate_proof_urls(public_post_url, receipt_proof_url, payment_proof_url, venue_photo_url)
        if url_warnings:
            print(f"  Warning for issue #{number}: URL validation issues:")
            for w in url_warnings:
                print(f"    - {w}")

        reviewed_at = today_iso()
        reviewer_id = "maintainer"

        # Determine initial paid_status
        # For new locations, bounty is held until 3 confirmations
        lr = loc_by_id.get(location_id)
        if is_new_location or (lr and lr.get("new_location_status") == "pending"):
            paid_status = "awaiting_confirmation"  # Held until location is confirmed
        else:
            paid_status = "pending"  # Ready for payout

        # Append to checks_public.csv
        chk_rows.append({
            "check_id": check_id,
            "location_id": location_id,
            "submitter_id": submitter_id,
            "submitted_at": submitted_at,
            "check_type": check_type,
            "public_post_url": public_post_url,
            "receipt_proof_url": receipt_proof_url,
            "payment_proof_url": payment_proof_url,
            "venue_photo_url": venue_photo_url,
            "proof_hash": "",
            "observations_public": observations,
            "suggested_updates": "",
            "review_status": "approved",
            "reviewed_at": reviewed_at,
            "reviewer_id": reviewer_id,
            "rejection_reason_public": "",
            "base_bounty_sats": str(base_bounty),
            "activity_factor": str(activity_factor),
            "final_bounty_sats": str(final_bounty),
            "paid_status": paid_status,
            "paid_at": "",
        })
        existing.add(check_id)
        appended += 1

        # Update locations.csv row
        lr = loc_by_id.get(location_id)
        if lr:
            lr["last_verified_at"] = reviewed_at
            lr["cooldown_until"] = add_days(reviewed_at, 90)
            lr["eligible_now"] = "no"
            lr["last_check_id"] = check_id
            try:
                new_count = int(lr.get("verified_by_count", "0") or "0") + 1
                lr["verified_by_count"] = str(new_count)
            except (ValueError, TypeError) as e:
                print(f"Warning: Could not parse verified_by_count for {location_id}: {e}")
                new_count = 1
                lr["verified_by_count"] = "1"

            # Handle new location confirmation tracking
            if lr.get("new_location_status") == "pending":
                if new_count >= 3:
                    lr["new_location_status"] = "confirmed"
                    lr["verification_confidence"] = "high"
                    print(f"New location {location_id} confirmed with {new_count} checks!")
                else:
                    lr["verification_confidence"] = "low"
                    print(f"New location {location_id} has {new_count}/3 confirmations")
            else:
                lr["verification_confidence"] = "medium"

            lr["last_updated_at"] = reviewed_at

    # Release held bounties for newly confirmed locations
    confirmed_locations = {r["location_id"] for r in loc_rows if r.get("new_location_status") == "confirmed"}
    bounties_released = 0
    for chk in chk_rows:
        if (chk.get("location_id") in confirmed_locations and
            chk.get("paid_status") == "awaiting_confirmation"):
            chk["paid_status"] = "pending"
            bounties_released += 1

    if appended == 0 and new_locations_added == 0:
        print("No new approved issues to apply.")
        return

    # Sort checks for nicer diffs
    chk_rows.sort(key=lambda r: (r.get("reviewed_at", ""), r.get("check_id", "")))

    write_csv(CHECKS, chk_rows, chk_fields)
    write_csv(LOCATIONS, loc_rows, loc_fields)

    print(f"Appended {appended} checks, added {new_locations_added} new locations.")
    if bounties_released > 0:
        print(f"Released {bounties_released} bounties for newly confirmed locations.")

if __name__ == "__main__":
    main()
