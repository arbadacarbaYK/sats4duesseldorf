#!/bin/bash
# Copy data files to docs/data for GitHub Pages
# This script is used by multiple workflows to ensure consistent data publishing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p docs/data

# Copy locations if exists
if [ -f "data/locations.csv" ]; then
  cp -f data/locations.csv docs/data/locations.csv
  echo "Copied locations.csv"
fi

# Copy and anonymize checks_public.csv (replace submitter_id with pseudonyms)
if [ -f "data/checks_public.csv" ]; then
  python3 "$SCRIPT_DIR/anonymize_csv.py" data/checks_public.csv docs/data/checks_public.csv
  echo "Copied and anonymized checks_public.csv"
fi

# Copy budget if exists
if [ -f "data/budget.json" ]; then
  cp -f data/budget.json docs/data/budget.json
  echo "Copied budget.json"
fi

# Copy leaderboard if exists
if [ -f "data/leaderboard.json" ]; then
  cp -f data/leaderboard.json docs/data/leaderboard.json
  echo "Copied leaderboard.json"
fi

echo "Data files copied to docs/data/"
