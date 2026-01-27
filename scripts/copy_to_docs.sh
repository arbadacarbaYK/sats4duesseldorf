#!/bin/bash
# Copy data files to docs/data for GitHub Pages
# This script is used by multiple workflows to ensure consistent data publishing

set -e

mkdir -p docs/data

# Copy locations if exists
if [ -f "data/locations.csv" ]; then
  cp -f data/locations.csv docs/data/locations.csv
  echo "Copied locations.csv"
fi

# Copy checks if exists
if [ -f "data/checks_public.csv" ]; then
  cp -f data/checks_public.csv docs/data/checks_public.csv
  echo "Copied checks_public.csv"
fi

# Copy budget if exists
if [ -f "data/budget.json" ]; then
  cp -f data/budget.json docs/data/budget.json
  echo "Copied budget.json"
fi

echo "Data files copied to docs/data/"
