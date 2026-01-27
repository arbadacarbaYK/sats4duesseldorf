#!/usr/bin/env python3
"""
Generate leaderboard.json from checks_public.csv.

Only includes approved AND paid checks.
Aggregates by pseudonym, sorted by total sats earned.
"""
import csv
import json
import hashlib
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Same pseudonym generation as anonymize_csv.py
ADJECTIVES = [
    "Clever", "Bright", "Brilliant", "Sharp", "Wise", "Savvy", "Astute", "Shrewd",
    "Keen", "Quick", "Witty", "Brainy", "Gifted", "Ingenious", "Nimble", "Insightful"
]

FIGURES = [
    "Satoshi", "Finney", "Szabo", "Back", "Nakamoto", "Andresen", "Maxwell", "Wuille", "Todd",
    "Diffie", "Hellman", "Rivest", "Shamir", "Merkle", "Chaum", "Schneier", "Bernstein",
    "Euler", "Gauss", "Turing", "Shannon", "Fermat", "Lovelace", "Noether", "Ramanujan", "Galois"
]


def generate_pseudonym(submitter_id: str) -> str:
    """Generate a deterministic pseudonym from a submitter_id."""
    if not submitter_id or submitter_id == "unknown":
        return "Anonymous"

    hash_bytes = hashlib.sha256(submitter_id.encode()).digest()
    adj_index = hash_bytes[0] % len(ADJECTIVES)
    fig_index = hash_bytes[1] % len(FIGURES)

    return f"{ADJECTIVES[adj_index]} {FIGURES[fig_index]}"


def generate_leaderboard():
    """Generate leaderboard from paid checks."""
    checks_path = Path("data/checks_public.csv")
    leaderboard_path = Path("data/leaderboard.json")

    if not checks_path.exists():
        print("No checks_public.csv found")
        return

    # Read checks
    with checks_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Aggregate by submitter
    participants = defaultdict(lambda: {
        "checks_count": 0,
        "total_sats": 0,
        "last_check_at": ""
    })

    for row in rows:
        # Only count approved AND paid checks
        if row.get("review_status") != "approved":
            continue
        if row.get("paid_status") != "paid":
            continue

        submitter_id = row.get("submitter_id", "").strip()
        if not submitter_id:
            continue

        pseudonym = generate_pseudonym(submitter_id)

        # Parse bounty
        try:
            sats = int(row.get("final_bounty_sats", 0) or 0)
        except ValueError:
            sats = 0

        # Get paid date
        paid_at = row.get("paid_at", "")

        participants[pseudonym]["checks_count"] += 1
        participants[pseudonym]["total_sats"] += sats

        # Track most recent check
        if paid_at > participants[pseudonym]["last_check_at"]:
            participants[pseudonym]["last_check_at"] = paid_at

    # Build sorted leaderboard (by sats desc, then by checks desc)
    leaderboard = []
    for pseudonym, stats in participants.items():
        leaderboard.append({
            "pseudonym": pseudonym,
            "checks_count": stats["checks_count"],
            "total_sats": stats["total_sats"],
            "last_check_at": stats["last_check_at"]
        })

    leaderboard.sort(key=lambda x: (-x["total_sats"], -x["checks_count"]))

    # Add ranks
    for i, entry in enumerate(leaderboard, 1):
        entry["rank"] = i

    # Build output
    output = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "total_participants": len(leaderboard),
        "total_checks_paid": sum(p["checks_count"] for p in leaderboard),
        "total_sats_paid": sum(p["total_sats"] for p in leaderboard),
        "leaderboard": leaderboard
    }

    # Write leaderboard
    with leaderboard_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Leaderboard generated: {len(leaderboard)} participants, {output['total_sats_paid']} sats paid")


if __name__ == "__main__":
    generate_leaderboard()
