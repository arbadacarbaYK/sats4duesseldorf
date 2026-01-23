#!/usr/bin/env python3
import os, re, csv, datetime, json
from pathlib import Path

# Files
LOCATIONS = Path("data/locations.csv")
CHECKS = Path("data/checks_public.csv")

# Env from GitHub Actions
GITHUB_EVENT_PATH = os.environ.get("GITHUB_EVENT_PATH", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "")

APPROVED_MARKER = re.compile(r"^SFB-APPROVED\s+(.*)$", re.MULTILINE)
KV = re.compile(r"(\w+)=([^\s]+)")

def today_iso():
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

def parse_approved_line(text: str):
    m = APPROVED_MARKER.search(text or "")
    if not m:
        return None
    blob = m.group(1)
    data = dict(KV.findall(blob))
    # required keys
    required = ["check_id","reviewed_at","reviewer_id","base_bounty_sats","activity_factor","final_bounty_sats"]
    if not all(k in data for k in required):
        return None
    return data

def main():
    # This script expects to be run with a JSON file listing issues pulled earlier.
    issues_path = Path("data/_approved_issues.json")
    if not issues_path.exists():
        print("No approved issues payload found. Nothing to do.")
        return

    issues = json.loads(issues_path.read_text(encoding="utf-8"))
    if not issues:
        print("No approved issues. Nothing to do.")
        return

    loc_rows, loc_fields = read_csv(LOCATIONS)
    chk_rows, chk_fields = read_csv(CHECKS)

    # Index for quick lookup
    loc_by_id = {r["location_id"]: r for r in loc_rows}
    existing_check_ids = {r["check_id"] for r in chk_rows if r.get("check_id")}

    appended = 0
    updated_locations = 0

    for issue in issues:
        body = issue.get("body") or ""
        comments = issue.get("comments_text") or ""
        text = body + "\n" + comments

        approved = parse_approved_line(text)
        if not approved:
            continue

        check_id = approved["check_id"]
        if check_id in existing_check_ids:
            continue  # already applied

        # We rely on template fields in issue body (simple regex)
        def find_field(label):
            # matches "Location-ID ...\n<value>"
            pat = re.compile(rf"{re.escape(label)}\s*\n+([^\n]+)", re.IGNORECASE)
            mm = pat.search(body)
            return (mm.group(1).strip() if mm else "")

        location_id = find_field("Location-ID (aus locations.csv)") or find_field("Location-ID")
        submitted_at = find_field("Datum/Uhrzeit des Kaufs") or ""
        check_type = "base"
        if "critical_change" in (issue.get("labels") or []):
            check_type = "critical_change"
        # also try dropdown text:
        ct = find_field("Check-Typ")
        if ct in ("base","critical_change"):
            check_type = ct

        public_post_url = find_field("Öffentlicher Beweis-Post") or ""
        receipt_proof_url = find_field("Beleg (Bon)") or ""
        payment_proof_url = find_field("Bitcoin-Zahlungsnachweis") or ""
        venue_photo_url = find_field("Ort erkennbar") or ""
        observations = find_field("Beobachtungen (kurz)") or ""
        suggested_updates = ""
        # multi-line textarea for updates
        m_upd = re.search(r"Änderungsbedarf am Eintrag\?\s*\(optional\)\s*\n+([\s\S]+)$", body, re.IGNORECASE)
        if m_upd:
            suggested_updates = m_upd.group(1).strip()

        # Write check row (public)
        chk_rows.append({
            "check_id": check_id,
            "location_id": location_id,
            "submitted_at": submitted_at,
            "check_type": check_type,
            "public_post_url": public_post_url,
            "receipt_proof_url": receipt_proof_url,
            "payment_proof_url": payment_proof_url,
            "venue_photo_url": venue_photo_url,
            "proof_hash": "",  # optional later
            "observations_public": observations,
            "suggested_updates": suggested_updates,
            "review_status": "approved",
            "reviewed_at": approved["reviewed_at"],
            "reviewer_id": approved["reviewer_id"],
            "rejection_reason_public": "",
            "base_bounty_sats": approved["base_bounty_sats"],
            "activity_factor": approved["activity_factor"],
            "final_bounty_sats": approved["final_bounty_sats"],
            "paid_status": "pending",
            "paid_at": "",
        })
        existing_check_ids.add(check_id)
        appended += 1

        # Update location
        if location_id and location_id in loc_by_id:
            lr = loc_by_id[location_id]
            # set verification date = reviewed_at date
            last = approved["reviewed_at"]
            lr["last_verified_at"] = last
            lr["cooldown_until"] = add_days(last, 90)
            lr["eligible_now"] = "no"
            lr["last_check_id"] = check_id
            # bump count
            try:
                lr["verified_by_count"] = str(int(lr.get("verified_by_count","0") or "0") + 1)
            except:
                lr["verified_by_count"] = "1"
            lr["verification_confidence"] = "medium"
            lr["last_updated_at"] = today_iso()
            updated_locations += 1

    # Sort checks by submitted_at then check_id (nice)
    chk_rows.sort(key=lambda r: (r.get("submitted_at",""), r.get("check_id","")))

    write_csv(CHECKS, chk_rows, chk_fields)
    write_csv(LOCATIONS, loc_rows, loc_fields)

    print(f"Appended checks: {appended}, updated locations: {updated_locations}")

if __name__ == "__main__":
    main()
