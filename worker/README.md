# sats4berlin Form Handler

Cloudflare Worker that processes Tally form submissions, creates GitHub issues with public data, and stores private contact information in Cloudflare KV for later payout.

## Architecture

```
Tally Form → Cloudflare Worker → GitHub Issue (public)
                    ↓
              Cloudflare KV (private contact info)
                    ↓
           Maintainer retrieves contact → Cashu payout
```

## Setup

### 1. Prerequisites

- Cloudflare account
- Node.js 18+
- Wrangler CLI: `npm install -g wrangler`

### 2. Authenticate with Cloudflare

```bash
wrangler login
```

Or use API token:
```bash
export CLOUDFLARE_API_TOKEN=your_token_here
```

### 3. Create KV Namespace

```bash
cd worker
wrangler kv:namespace create "PRIVATE_DATA"
```

Copy the namespace ID from the output and update `wrangler.toml`:
```toml
[[kv_namespaces]]
binding = "PRIVATE_DATA"
id = "YOUR_NAMESPACE_ID_HERE"
```

### 4. Set Secrets

```bash
# GitHub Personal Access Token (needs repo scope)
wrangler secret put GITHUB_TOKEN

# Admin API token (generate a secure random string)
wrangler secret put ADMIN_API_TOKEN
```

### 5. Deploy

```bash
npm run deploy
```

The worker will be available at: `https://sats4berlin-form-handler.<your-subdomain>.workers.dev`

## Tally Form Setup

Create two forms in Tally:

### Form 1: Check einreichen

Fields (use these exact IDs):
- `location_id` (Text) - Location ID from the list
- `date_time` (Text) - Date and time of purchase
- `check_type` (Dropdown) - "Normal" or "Kritisch"
- `public_post_url` (URL) - Public social media post
- `receipt_proof_url` (URL) - Receipt photo link
- `payment_proof_url` (URL) - Payment confirmation link
- `venue_photo_url` (URL) - Venue photo link
- `observations` (Long text) - How did the payment go?
- `suggested_updates` (Long text) - Optional updates
- `contact_method` (Dropdown) - "Lightning Address", "Cashu", "Nostr DM"
- `contact_value` (Text) - The actual address/npub

### Form 2: Neuen Ort melden

Fields:
- `name` (Text) - Name of the location
- `address` (Text) - Full address
- `category` (Dropdown) - Category
- `website` (URL) - Optional website
- `osm_url` (URL) - Optional OSM link
- `date_time` (Text) - Date and time of purchase
- `public_post_url` (URL) - Public post
- `receipt_proof_url` (URL) - Receipt
- `payment_proof_url` (URL) - Payment proof
- `venue_photo_url` (URL) - Venue photo
- `notes` (Long text) - Experience description
- `contact_method` (Dropdown) - Payout method
- `contact_value` (Text) - Payout address

### Webhook Configuration

In Tally form settings → Integrations → Webhooks:
- URL: `https://sats4berlin-form-handler.<subdomain>.workers.dev/webhook/tally`
- Method: POST

## Admin API

### Get Contact Info

```bash
curl -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  "https://sats4berlin-form-handler.<subdomain>.workers.dev/admin/contact?submission_id=SUB-XXXXX"
```

Response:
```json
{
  "submissionId": "SUB-XXXXX",
  "contact_method": "Lightning Address",
  "contact_value": "user@getalby.com",
  "submittedAt": "2026-01-25T12:00:00Z"
}
```

### Mark as Paid

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"submission_id": "SUB-XXXXX", "delete_data": true}' \
  "https://sats4berlin-form-handler.<subdomain>.workers.dev/admin/mark-paid"
```

## Cashu Payout Flow

1. Submission is approved (maintainer adds `approved` label)
2. Maintainer retrieves contact info via Admin API
3. Based on `contact_method`:
   - **Lightning Address**: Send sats directly
   - **Cashu**: Mint tokens and send via preferred channel
   - **Nostr DM**: Send Cashu tokens via encrypted DM
4. Mark as paid via Admin API

### Recommended Cashu Mints

For minting Cashu tokens:

1. **cashu.me** - Simple web interface, good for small amounts
2. **Minibits** (minibits.cash) - Mobile app with mint
3. **eNuts** - Another mobile option
4. **Self-hosted Nutshell** - For full control

To send Cashu tokens:
```
cashu://u?token=cashuAey...
```

## Security Notes

- Private contact data is stored with 90-day TTL
- Admin API requires Bearer token authentication
- GitHub token should have minimal required scopes (repo only)
- Consider IP allowlisting for admin endpoints

## Development

```bash
# Run locally
npm run dev

# View logs
npm run tail
```
