#!/usr/bin/env python3
"""
Anonymize submitter_id in checks_public.csv for public display.

Replaces USER-XXXX hashes with deterministic pseudonyms like "Bright Finney"
based on Bitcoin, cryptography, and mathematics pioneers.
"""
import csv
import hashlib
import sys
from pathlib import Path

# Adjectives (smart/clever variations)
ADJECTIVES = [
    "Clever", "Bright", "Brilliant", "Sharp", "Wise", "Savvy", "Astute", "Shrewd",
    "Keen", "Quick", "Witty", "Brainy", "Gifted", "Ingenious", "Nimble", "Insightful"
]

# Important figures from Bitcoin, cryptography, and mathematics
FIGURES = [
    # Bitcoin pioneers
    "Satoshi", "Finney", "Szabo", "Back", "Nakamoto", "Andresen", "Maxwell", "Wuille", "Todd",
    # Cryptography pioneers
    "Diffie", "Hellman", "Rivest", "Shamir", "Merkle", "Chaum", "Schneier", "Bernstein",
    # Mathematics/CS pioneers
    "Euler", "Gauss", "Turing", "Shannon", "Fermat", "Lovelace", "Noether", "Ramanujan", "Galois"
]


def generate_pseudonym(submitter_id: str) -> str:
    """
    Generate a deterministic pseudonym from a submitter_id.
    Same input always produces the same output.
    """
    if not submitter_id or submitter_id == "unknown":
        return "Anonymous"

    # Hash the submitter_id to get consistent indices
    hash_bytes = hashlib.sha256(submitter_id.encode()).digest()

    # Use first bytes for adjective, next bytes for figure
    adj_index = hash_bytes[0] % len(ADJECTIVES)
    fig_index = hash_bytes[1] % len(FIGURES)

    return f"{ADJECTIVES[adj_index]} {FIGURES[fig_index]}"


def anonymize_csv(input_path: Path, output_path: Path):
    """
    Read a CSV, replace submitter_id with pseudonyms, write to output.
    """
    with input_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    if not fieldnames:
        print(f"Error: No fieldnames in {input_path}")
        return False

    # Check if submitter_id column exists
    if "submitter_id" not in fieldnames:
        print(f"Warning: No submitter_id column in {input_path}, copying as-is")
        with output_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return True

    # Transform submitter_id to pseudonyms
    pseudonym_count = 0
    for row in rows:
        original_id = row.get("submitter_id", "")
        if original_id and original_id != "unknown":
            row["submitter_id"] = generate_pseudonym(original_id)
            pseudonym_count += 1

    # Write output
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Anonymized {pseudonym_count} submitter IDs")
    return True


def main():
    if len(sys.argv) < 3:
        print("Usage: anonymize_csv.py <input.csv> <output.csv>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    success = anonymize_csv(input_path, output_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
