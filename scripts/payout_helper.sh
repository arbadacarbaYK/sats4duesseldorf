#!/bin/bash
# Payout Helper Script for sats4berlin
#
# This script helps maintainers process payouts by:
# 1. Fetching contact info from the Cloudflare Worker
# 2. Displaying payout instructions
# 3. Marking payouts as complete

set -e

# Configuration - update these!
WORKER_URL="${WORKER_URL:-https://sats4berlin-form-handler.your-subdomain.workers.dev}"
ADMIN_TOKEN="${ADMIN_TOKEN:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  get <submission_id>     Get contact info for a submission"
    echo "  paid <submission_id>    Mark a submission as paid"
    echo "  list-pending            List pending payouts from checks_public.csv"
    echo ""
    echo "Environment variables:"
    echo "  WORKER_URL    - Cloudflare Worker URL"
    echo "  ADMIN_TOKEN   - Admin API token"
    echo ""
    echo "Example:"
    echo "  export ADMIN_TOKEN='your_token_here'"
    echo "  $0 get SUB-XXXXX"
    exit 1
}

check_config() {
    if [ -z "$ADMIN_TOKEN" ]; then
        echo -e "${RED}Error: ADMIN_TOKEN not set${NC}"
        echo "Run: export ADMIN_TOKEN='your_token_here'"
        exit 1
    fi
}

get_contact() {
    local submission_id="$1"
    check_config

    echo -e "${YELLOW}Fetching contact info for: $submission_id${NC}"
    echo ""

    response=$(curl -s -w "\n%{http_code}" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        "$WORKER_URL/admin/contact?submission_id=$submission_id")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" = "200" ]; then
        echo -e "${GREEN}Contact info found:${NC}"
        echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"

        # Extract and display payout method
        method=$(echo "$body" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('contact_method',''))" 2>/dev/null || echo "")
        value=$(echo "$body" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('contact_value',''))" 2>/dev/null || echo "")

        if [ -n "$method" ] && [ -n "$value" ]; then
            echo ""
            echo -e "${GREEN}=== Payout Instructions ===${NC}"
            case "$method" in
                *Lightning*)
                    echo "Send Lightning payment to: $value"
                    ;;
                *Cashu*|*eCash*)
                    echo "Send Cashu tokens to: $value"
                    echo "Mint tokens at cashu.me or your preferred mint"
                    ;;
                *Nostr*)
                    echo "Send encrypted DM to: $value"
                    echo "Include Cashu token in the message"
                    ;;
                *)
                    echo "Method: $method"
                    echo "Value: $value"
                    ;;
            esac
        fi
    elif [ "$http_code" = "404" ]; then
        echo -e "${YELLOW}Submission not found or expired.${NC}"
        echo "This may be a GitHub-only submission (contact info in email)."
    else
        echo -e "${RED}Error ($http_code): $body${NC}"
    fi
}

mark_paid() {
    local submission_id="$1"
    check_config

    echo -e "${YELLOW}Marking as paid: $submission_id${NC}"

    response=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"submission_id\": \"$submission_id\", \"delete_data\": false}" \
        "$WORKER_URL/admin/mark-paid")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" = "200" ]; then
        echo -e "${GREEN}Success: $body${NC}"
    else
        echo -e "${RED}Error ($http_code): $body${NC}"
    fi
}

list_pending() {
    local csv_file="data/checks_public.csv"

    if [ ! -f "$csv_file" ]; then
        echo -e "${RED}Error: $csv_file not found${NC}"
        echo "Run from the repository root directory."
        exit 1
    fi

    echo -e "${YELLOW}Pending payouts:${NC}"
    echo ""

    # Header
    printf "%-15s %-15s %-12s %-10s\n" "CHECK_ID" "LOCATION_ID" "BOUNTY" "STATUS"
    printf "%-15s %-15s %-12s %-10s\n" "--------" "-----------" "------" "------"

    # Parse CSV (skip header)
    tail -n +2 "$csv_file" | while IFS=, read -r check_id location_id submitter_id submitted_at check_type \
        public_post receipt payment venue hash obs updates status reviewed_at reviewer_id \
        rejection base_bounty activity_factor final_bounty paid_status paid_at; do

        if [ "$paid_status" = "pending" ] || [ "$paid_status" = "awaiting_confirmation" ]; then
            printf "%-15s %-15s %-12s %-10s\n" "$check_id" "$location_id" "${final_bounty} sats" "$paid_status"
        fi
    done

    echo ""
    echo -e "${GREEN}To process a payout:${NC}"
    echo "  1. Find the Submission ID in the GitHub issue body"
    echo "  2. Run: $0 get SUB-XXXXX"
    echo "  3. Send the bounty to the contact address"
    echo "  4. Run: $0 paid SUB-XXXXX"
    echo "  5. Add the 'paid' label to the GitHub issue"
}

# Main
case "${1:-}" in
    get)
        [ -z "${2:-}" ] && usage
        get_contact "$2"
        ;;
    paid)
        [ -z "${2:-}" ] && usage
        mark_paid "$2"
        ;;
    list-pending|list)
        list_pending
        ;;
    *)
        usage
        ;;
esac
