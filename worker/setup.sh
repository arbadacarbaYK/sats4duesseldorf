#!/bin/bash
# Setup script for sats4berlin Cloudflare Worker

set -e

echo "=== sats4berlin Worker Setup ==="
echo ""

# Check if wrangler is installed
if ! command -v wrangler &> /dev/null; then
    echo "Installing wrangler..."
    npm install -g wrangler
fi

# Install dependencies
echo "Installing dependencies..."
npm install

# Create KV namespace
echo ""
echo "Creating KV namespace..."
KV_OUTPUT=$(wrangler kv:namespace create "PRIVATE_DATA" 2>&1) || true
echo "$KV_OUTPUT"

# Extract namespace ID
KV_ID=$(echo "$KV_OUTPUT" | grep -oP 'id = "\K[^"]+' || echo "")

if [ -n "$KV_ID" ]; then
    echo ""
    echo "Updating wrangler.toml with KV namespace ID: $KV_ID"
    sed -i "s/id = \"TO_BE_FILLED_AFTER_CREATION\"/id = \"$KV_ID\"/" wrangler.toml
else
    echo ""
    echo "Could not extract KV namespace ID. Please update wrangler.toml manually."
fi

echo ""
echo "=== Next Steps ==="
echo ""
echo "1. Set the required secrets:"
echo "   wrangler secret put GITHUB_TOKEN"
echo "   (Enter a GitHub Personal Access Token with 'repo' scope)"
echo ""
echo "   wrangler secret put ADMIN_API_TOKEN"
echo "   (Generate a secure random string, e.g.: openssl rand -hex 32)"
echo ""
echo "2. Deploy the worker:"
echo "   npm run deploy"
echo ""
echo "3. Set up Tally forms with webhook URL:"
echo "   https://sats4berlin-form-handler.<your-subdomain>.workers.dev/webhook/tally"
echo ""
echo "4. Test the health endpoint:"
echo "   curl https://sats4berlin-form-handler.<your-subdomain>.workers.dev/health"
echo ""
