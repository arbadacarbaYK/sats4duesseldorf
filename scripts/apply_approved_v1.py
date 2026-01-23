#!/usr/bin/env python3
import json
import re
import csv
import datetime
from pathlib import Path

LOCATIONS = Path("data/locations.csv")
CHECKS = Path("data/checks_public.csv")
APPROVED_ISSUES = Path("data/_approved_issues.json")

def today_iso() -> str:
    return datetime.date.today().isoformat()

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

    loc_by_id = {r["location_id"]: r for r in loc_rows}
    existing = {r["check_id"] for r in chk_rows if r.get("check_id")}

    appended = 0

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

        # Extract location_id (if absent, skip)
        location_id = (
            body_field(body, "Location-ID (aus locations.csv)")
            or body_field(body, "Location-ID")
        )
        if not location_id:
            continue

        # Deterministic check id from issue number (no duplicates)
        check_id = f"ISSUE-{number}"
        if check_id in existing:
            continue

        # Determine type & bounty
        check_type = body_field(body, "Check-Typ").strip().lower()
        if check_type not in ("base", "critical_change"):
            check_type = "critical_change" if "critical-change" in labels else "base"
        base_bounty = "21000" if check_type == "critical_change" else "10000"

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
        observations = body_field(body, "Beobachtungen (kurz)") or ""

        reviewed_at = today_iso()
        reviewer_id = "maintainer"

        # Append to checks_public.csv
        chk_rows.append({
            "check_id": check_id,
            "location_id": location_id,
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
            "base_bounty_sats": base_bounty,
            "activity_factor": "1.0",
            "final_bounty_sats": base_bounty,
            "paid_status": "pending",
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
                lr["verified_by_count"] = str(int(lr.get("verified_by_count", "0") or "0") + 1)
            except Exception:
                lr["verified_by_count"] = "1"
            lr["verification_confidence"] = "medium"
            lr["last_updated_at"] = reviewed_at

    if appended == 0:
        print("No new approved issues to apply.")
        return

    # Sort checks for nicer diffs
    chk_rows.sort(key=lambda r: (r.get("reviewed_at", ""), r.get("check_id", "")))

    write_csv(CHECKS, chk_rows, chk_fields)
    write_csv(LOCATIONS, loc_rows, loc_fields)

    print(f"Appended {appended} checks and updated locations.")

if __name__ == "__main__":
    main()
