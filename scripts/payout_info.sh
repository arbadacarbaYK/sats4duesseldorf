#!/bin/bash
# Payout Info Script - Get all payout details for an issue
#
# Usage: ./scripts/payout_info.sh <issue_number>
#
# Requires: ADMIN_TOKEN environment variable

set -e

WORKER_URL="${WORKER_URL:-https://sats4berlin-form-handler.satoshiinberlin.workers.dev}"
ADMIN_TOKEN="${ADMIN_TOKEN:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

if [ -z "$1" ]; then
    echo "Usage: $0 <issue_number>"
    echo "Example: $0 17"
    exit 1
fi

ISSUE_NUMBER="$1"

echo ""
echo -e "${BOLD}════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  PAYOUT INFO FOR ISSUE #${ISSUE_NUMBER}${NC}"
echo -e "${BOLD}════════════════════════════════════════════════════════${NC}"
echo ""

# Pull latest data from remote
echo -e "${YELLOW}Syncing latest data...${NC}"
git pull --quiet 2>/dev/null || echo -e "${YELLOW}Note: Could not pull latest changes${NC}"
echo ""

# Fetch issue details
echo -e "${YELLOW}Fetching issue details...${NC}"
TITLE=$(gh issue view "$ISSUE_NUMBER" --json title -q '.title' 2>/dev/null)
BODY=$(gh issue view "$ISSUE_NUMBER" --json body -q '.body' 2>/dev/null)
LABELS=$(gh issue view "$ISSUE_NUMBER" --json labels -q '.labels[].name' 2>/dev/null | tr '\n' ', ' | sed 's/,$//')

if [ -z "$TITLE" ]; then
    echo -e "${RED}Error: Could not fetch issue #${ISSUE_NUMBER}${NC}"
    exit 1
fi

echo -e "${CYAN}Title:${NC} $TITLE"
echo -e "${CYAN}Labels:${NC} $LABELS"
echo ""

# Extract submission ID and submitter info
SUBMISSION_ID=$(echo "$BODY" | grep -oP 'Submission ID:\*\*\s*`\K[^`]+' || echo "")
# Try new format "Submitter Ref" first, then fall back to old "Submitter ID"
SUBMITTER_ID=$(echo "$BODY" | grep -oP 'Submitter Ref:\*\*\s*`\K[^`]+' || \
               echo "$BODY" | grep -oP 'Submitter ID:\*\*\s*`\K[^`]+' || echo "")
PSEUDONYM=$(echo "$BODY" | grep -oP 'Submitter:\*\*\s*\K[^\n]+' || echo "")
LOCATION_ID=$(echo "$BODY" | grep -oP '### Location-ID\s+\K[A-Z]{2}-[A-Z]{2}-\d+' || \
              echo "$BODY" | grep -oP 'DE-BE-\d{5}' | head -1 || echo "")

echo -e "${CYAN}Submission ID:${NC} ${SUBMISSION_ID:-Not found (GitHub submission)}"
echo -e "${CYAN}Submitter:${NC}     ${PSEUDONYM:-Anonymous}"
echo -e "${CYAN}Submitter Ref:${NC} ${SUBMITTER_ID:-Not found}"
echo -e "${CYAN}Location ID:${NC}   ${LOCATION_ID:-Not found}"
echo ""

# Check if critical change
IS_CRITICAL=""
if echo "$LABELS" | grep -q "critical"; then
    IS_CRITICAL="true"
    echo -e "${YELLOW}⚠️  This is a CRITICAL CHANGE submission${NC}"
    echo ""
fi

# Calculate bounty from CSV
echo -e "${BOLD}── Bounty Calculation ──${NC}"

CHECK_ID="ISSUE-${ISSUE_NUMBER}"
CSV_ROW=$(grep "^${CHECK_ID}," data/checks_public.csv 2>/dev/null || echo "")

if [ -n "$CSV_ROW" ]; then
    # Parse CSV row (check_id is col 1, final_bounty_sats is col 18)
    BASE_BOUNTY=$(echo "$CSV_ROW" | cut -d',' -f17)
    ACTIVITY_FACTOR=$(echo "$CSV_ROW" | cut -d',' -f18)
    FINAL_BOUNTY=$(echo "$CSV_ROW" | cut -d',' -f19)
    PAID_STATUS=$(echo "$CSV_ROW" | cut -d',' -f20)

    echo -e "${CYAN}Base Bounty:${NC}      ${BASE_BOUNTY} sats"
    echo -e "${CYAN}Activity Factor:${NC}  ${ACTIVITY_FACTOR}x"
    echo -e "${GREEN}${BOLD}Final Payout:${NC}     ${GREEN}${BOLD}${FINAL_BOUNTY} sats${NC}"
    echo -e "${CYAN}Paid Status:${NC}      ${PAID_STATUS}"
else
    # Fallback calculation
    if [ -n "$IS_CRITICAL" ]; then
        echo -e "${GREEN}${BOLD}Final Payout:${NC}     ${GREEN}${BOLD}21,000 sats${NC} (critical change)"
    else
        echo -e "${YELLOW}Check not found in CSV - run approval workflow first${NC}"
    fi
fi
echo ""

# Get contact info
echo -e "${BOLD}── Contact Information ──${NC}"

if [ -z "$SUBMISSION_ID" ]; then
    echo -e "${YELLOW}No Submission ID found - this was submitted via GitHub directly.${NC}"
    echo "Contact info must be requested manually via the issue comments."
elif [ -z "$ADMIN_TOKEN" ]; then
    echo -e "${RED}ADMIN_TOKEN not set. Run:${NC}"
    echo "  export ADMIN_TOKEN='your_token_here'"
    echo ""
    echo "Then fetch contact info with:"
    echo "  curl -H \"Authorization: Bearer \$ADMIN_TOKEN\" \\"
    echo "    \"${WORKER_URL}/admin/contact?submission_id=${SUBMISSION_ID}\""
else
    # Fetch contact info from worker
    RESPONSE=$(curl -s -w "\n%{http_code}" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        "${WORKER_URL}/admin/contact?submission_id=${SUBMISSION_ID}")

    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
    CONTACT_JSON=$(echo "$RESPONSE" | sed '$d')

    if [ "$HTTP_CODE" = "200" ]; then
        METHOD=$(echo "$CONTACT_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('contact_method',''))" 2>/dev/null || echo "")
        VALUE=$(echo "$CONTACT_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('contact_value',''))" 2>/dev/null || echo "")

        echo -e "${CYAN}Method:${NC}  ${METHOD}"
        echo -e "${CYAN}Address:${NC} ${GREEN}${BOLD}${VALUE}${NC}"
        echo ""

        # Show payout instructions based on method
        echo -e "${BOLD}── Payout Instructions ──${NC}"
        case "$METHOD" in
            lightning)
                echo -e "Send Lightning payment to: ${GREEN}${BOLD}${VALUE}${NC}"
                ;;
            bolt12)
                echo -e "Pay BOLT12 offer: ${GREEN}${BOLD}${VALUE}${NC}"
                echo "  lightning-cli fetchinvoice <offer> <amount_msat>"
                echo "  lightning-cli pay <invoice>"
                ;;
            nostr)
                echo "Send encrypted Nostr DM with Cashu token to: ${VALUE}"
                ;;
            email)
                echo "Send email with Cashu token to: ${VALUE}"
                ;;
            telegram)
                echo "Send Telegram DM with Cashu token to: ${VALUE}"
                ;;
            signal)
                echo "Send Signal DM with Cashu token to username: ${VALUE}"
                ;;
            simplex)
                echo "Send SimpleX message with Cashu token to: ${VALUE}"
                ;;
            *)
                echo "Method: ${METHOD}"
                echo "Address: ${VALUE}"
                ;;
        esac
    elif [ "$HTTP_CODE" = "404" ]; then
        echo -e "${YELLOW}Submission not found or expired in KV store.${NC}"
    else
        echo -e "${RED}Error fetching contact info (HTTP ${HTTP_CODE}): ${CONTACT_JSON}${NC}"
    fi
fi

echo ""
echo -e "${BOLD}── After Payout ──${NC}"
echo "1. Add 'paid' label to close the issue:"
echo -e "   ${CYAN}gh issue edit ${ISSUE_NUMBER} --add-label paid${NC}"
echo ""
