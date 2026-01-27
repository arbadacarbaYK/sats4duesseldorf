# sats4berlin Form Handler

Cloudflare Worker that processes form submissions from the self-hosted submission form, creates GitHub issues with public data, and stores private contact information in Cloudflare KV for payout.

## Architecture

```
Submit Form (GitHub Pages) → Cloudflare Worker → GitHub Issue (public)
                                    ↓
                              Cloudflare KV (private contact info)
                                    ↓
                           Maintainer retrieves contact → Payout
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

## Self-Hosted Form

The submission form is hosted on GitHub Pages at `docs/submit.html`. It posts directly to the worker's `/api/submit` endpoint.

### Form Fields

**Check submission:**
- `location_id` - Location ID from the list
- `date_time` - Date and time of purchase
- `check_type` - "normal" or "critical"
- `public_post_url` - Public social media post
- `receipt_proof_url` - Receipt photo link
- `payment_proof_url` - Payment confirmation link
- `venue_photo_url` - Venue photo link
- `observations` - How did the payment go?
- `suggested_updates` - Optional updates
- `contact_method` - Payout method (lightning, nostr, email, telegram, simplex)
- `contact_value` - The actual contact address

**New location submission:**
- `name` - Name of the location
- `address` - Full address
- `category` - Category
- `website` - Optional website
- `osm_url` - Optional OSM link
- Plus all the proof and contact fields above

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
  "submitterId": "USER-00ACE844FD9A",
  "contact_method": "lightning",
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

## Payout Methods

| Method | Contact Format | How to Pay |
|--------|---------------|------------|
| Lightning | `name@getalby.com` | Send sats directly |
| Nostr | `npub1...` | Encrypted DM with Cashu token |
| Email | `user@example.com` | Send Cashu token via email |
| Telegram | `@username` | Send Cashu token via DM |
| SimpleX | Invite link | Send Cashu token via chat |

### Cashu Token Creation

Use [cashu.me](https://cashu.me) or a mobile wallet like Minibits to mint tokens.

## Submitter Identity

Each submission includes:
- **Pseudonym**: A human-readable name shown publicly (e.g., "Savvy Schneier")
- **Submitter Ref**: A `USER-XXXX` identifier stored internally for tracking

The pseudonym is derived deterministically from the submitter ref using SHA-256, so the same person always gets the same pseudonym. This enables:
- Activity multiplier tracking (same person = same ID)
- Pseudonymous identity (contact details not exposed)
- Human-readable attribution in GitHub issues

## Security Notes

- Private contact data is stored with 90-day TTL
- Admin API requires Bearer token authentication (minimum 16 characters)
- Admin API validates Origin header and logs all access for audit trail
- Form submissions are protected by Origin validation (CSRF protection)
- Rate limiting: 10 submissions per hour per IP (sliding window)
- GitHub token should have minimal required scopes (repo only)
- Submitter Ref (USER-XXXX) is a truncated SHA-256 hash (not reversible)

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Yes | GitHub PAT with repo scope |
| `ADMIN_API_TOKEN` | Yes | Admin API token (min 16 chars) |
| `ALLOWED_ORIGINS_DEV` | No | Comma-separated dev origins for testing |
| `ADMIN_ALLOWED_ORIGINS_DEV` | No | Comma-separated dev origins for admin API |

## Development

```bash
# Run locally
npm run dev

# View logs
npm run tail
```
