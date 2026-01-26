/**
 * sats4berlin Form Handler
 *
 * Receives form submissions, creates GitHub issues with public data,
 * and stores private contact information in Cloudflare KV.
 */

import { handleAdminRequest } from './admin.js';

// Allowed origins for CORS/CSRF protection
// Note: Add localhost origins via ALLOWED_ORIGINS_DEV env var for local testing
const ALLOWED_ORIGINS = [
  'https://satoshiinberlin.github.io',
];

// Rate limiting configuration
const RATE_LIMIT_WINDOW_MS = 60 * 60 * 1000; // 1 hour
const RATE_LIMIT_MAX_REQUESTS = 10; // Max 10 submissions per hour per IP

// Field mappings from form field names to our internal names
const FIELD_MAPPING = {
  // Check submission fields
  'location_id': 'location_id',
  'date_time': 'date_time',
  'check_type': 'check_type',
  'public_post_url': 'public_post_url',
  'receipt_proof_url': 'receipt_proof_url',
  'payment_proof_url': 'payment_proof_url',
  'venue_photo_url': 'venue_photo_url',
  'observations': 'observations',
  'suggested_updates': 'suggested_updates',
  // Critical change fields (for reporting locations that no longer accept BTC)
  'critical_evidence_url': 'critical_evidence_url',
  'critical_post_url': 'critical_post_url',
  // New location fields
  'name': 'name',
  'address': 'address',
  'category': 'category',
  'website': 'website',
  'osm_url': 'osm_url',
  'notes': 'notes',
  // Private fields (stored in KV only)
  'contact_method': 'contact_method',
  'contact_value': 'contact_value',
};

// Fields that should NOT be posted to GitHub (private)
const PRIVATE_FIELDS = ['contact_method', 'contact_value'];

// Fields that identify form type
// Note: For critical checks, public_post_url is optional, but critical_evidence_url is required
const CHECK_BASE_REQUIRED_FIELDS = ['location_id', 'date_time'];
const CHECK_NORMAL_REQUIRED_FIELDS = ['public_post_url'];
const CHECK_CRITICAL_REQUIRED_FIELDS = ['critical_evidence_url'];
const NEW_LOCATION_REQUIRED_FIELDS = ['name', 'address', 'category'];

// Cache for valid location IDs (refreshed every 5 minutes)
let locationIdCache = { ids: new Set(), lastFetched: 0 };
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Health check endpoint (GET)
    if (url.pathname === '/health') {
      return new Response(JSON.stringify({ status: 'ok', timestamp: new Date().toISOString() }), {
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // Admin API endpoints (GET/POST)
    if (url.pathname.startsWith('/admin/')) {
      return handleAdminRequest(request, env);
    }

    // Main webhook endpoint - POST only
    if (url.pathname !== '/api/submit') {
      return new Response('Not found', { status: 404 });
    }

    // Only accept POST requests for webhook
    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405 });
    }

    // CORS headers for the response
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*', // Will be overwritten if origin is allowed
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    // CSRF protection: Validate Origin header
    const origin = request.headers.get('Origin');
    // Allow dev origins if ALLOWED_ORIGINS_DEV is set (comma-separated)
    const devOrigins = env.ALLOWED_ORIGINS_DEV ? env.ALLOWED_ORIGINS_DEV.split(',') : [];
    const allAllowedOrigins = [...ALLOWED_ORIGINS, ...devOrigins];
    if (!origin || !allAllowedOrigins.some(allowed => origin.startsWith(allowed.trim()))) {
      return new Response(JSON.stringify({ error: 'Invalid origin' }), {
        status: 403,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    corsHeaders['Access-Control-Allow-Origin'] = origin;

    // Rate limiting: Sliding window using timestamps (more robust against race conditions)
    const clientIP = request.headers.get('CF-Connecting-IP') || 'unknown';
    const rateLimitKey = `ratelimit:${clientIP}`;
    const now = Date.now();

    try {
      const rateLimitData = await env.PRIVATE_DATA.get(rateLimitKey);
      let timestamps = [];

      if (rateLimitData) {
        const parsed = JSON.parse(rateLimitData);
        // Filter to only keep timestamps within the window
        timestamps = (parsed.timestamps || []).filter(ts => now - ts < RATE_LIMIT_WINDOW_MS);
      }

      // Check rate limit BEFORE adding new timestamp
      // This means even if concurrent requests read at the same time,
      // they'll all add timestamps and subsequent checks will count them
      if (timestamps.length >= RATE_LIMIT_MAX_REQUESTS) {
        const oldestTs = Math.min(...timestamps);
        const retryAfterSecs = Math.ceil((oldestTs + RATE_LIMIT_WINDOW_MS - now) / 1000);
        return new Response(JSON.stringify({
          error: 'Rate limit exceeded',
          message: 'Zu viele Einreichungen. Bitte warte eine Stunde.',
          retryAfter: retryAfterSecs
        }), {
          status: 429,
          headers: {
            'Content-Type': 'application/json',
            'Retry-After': String(retryAfterSecs),
            ...corsHeaders
          }
        });
      }

      // Add current request timestamp
      timestamps.push(now);

      // Store updated timestamps (keep max 2x limit to prevent unbounded growth)
      await env.PRIVATE_DATA.put(rateLimitKey, JSON.stringify({
        timestamps: timestamps.slice(-RATE_LIMIT_MAX_REQUESTS * 2)
      }), { expirationTtl: 3600 }); // Expire after 1 hour
    } catch (rateLimitError) {
      // Don't fail if rate limiting has issues, just log
      console.error('Rate limiting error:', rateLimitError);
    }

    try {
      // Parse the webhook payload
      const payload = await request.json();

      // Extract form data from the payload
      const formData = extractFormFields(payload);

      if (!formData || Object.keys(formData).length === 0) {
        return new Response(JSON.stringify({ error: 'No form data found' }), {
          status: 400,
          headers: { 'Content-Type': 'application/json', ...corsHeaders }
        });
      }

      // Validate location_id format if present
      if (formData.location_id && !/^DE-BE-\d{5}$/.test(formData.location_id)) {
        return new Response(JSON.stringify({ error: 'Invalid location ID format' }), {
          status: 400,
          headers: { 'Content-Type': 'application/json', ...corsHeaders }
        });
      }

      // Validate location exists (for check submissions)
      if (formData.location_id) {
        const validIds = await fetchValidLocationIds(env);
        if (validIds.size > 0 && !validIds.has(formData.location_id)) {
          return new Response(JSON.stringify({
            error: 'Location not found',
            message: `Location ${formData.location_id} existiert nicht in der Datenbank.`
          }), {
            status: 400,
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });
        }
      }

      // Validate date is not in the future
      if (formData.date_time) {
        const submittedDate = new Date(formData.date_time);
        if (submittedDate > new Date()) {
          return new Response(JSON.stringify({ error: 'Date cannot be in the future' }), {
            status: 400,
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });
        }
      }

      // Validate URL formats
      const urlFields = ['public_post_url', 'receipt_proof_url', 'payment_proof_url', 'venue_photo_url', 'website', 'osm_url', 'critical_evidence_url', 'critical_post_url'];
      for (const field of urlFields) {
        if (formData[field] && formData[field] !== '_nicht angegeben_') {
          try {
            new URL(formData[field]);
          } catch {
            return new Response(JSON.stringify({ error: `Invalid URL in ${field}` }), {
              status: 400,
              headers: { 'Content-Type': 'application/json', ...corsHeaders }
            });
          }
        }
      }

      // Determine form type
      const isNewLocation = NEW_LOCATION_REQUIRED_FIELDS.every(f => formData[f]);
      const hasCheckBaseFields = CHECK_BASE_REQUIRED_FIELDS.every(f => formData[f]);
      const isCriticalCheck = formData.check_type === 'critical';

      // Check submissions: base fields + either normal fields (for normal checks) or critical fields (for critical checks)
      let isCheck = false;
      if (hasCheckBaseFields) {
        if (isCriticalCheck) {
          // Critical checks require evidence URL
          isCheck = CHECK_CRITICAL_REQUIRED_FIELDS.every(f => formData[f]);
        } else {
          // Normal checks require public post URL
          isCheck = CHECK_NORMAL_REQUIRED_FIELDS.every(f => formData[f]);
        }
      }

      if (!isNewLocation && !isCheck) {
        return new Response(JSON.stringify({ error: 'Invalid form data - missing required fields' }), {
          status: 400,
          headers: { 'Content-Type': 'application/json', ...corsHeaders }
        });
      }

      // Generate a unique submission ID
      const submissionId = generateSubmissionId();

      // Separate public and private data
      const publicData = {};
      const privateData = {};

      for (const [key, value] of Object.entries(formData)) {
        if (PRIVATE_FIELDS.includes(key)) {
          privateData[key] = value;
        } else {
          publicData[key] = value;
        }
      }

      // Generate submitter_id from contact info (for activity multiplier tracking)
      // This creates a consistent but pseudonymous identifier
      let submitterId = null;
      if (privateData.contact_method && privateData.contact_value) {
        const contactString = `${privateData.contact_method}:${privateData.contact_value}`.toLowerCase().trim();
        submitterId = await generateSubmitterId(contactString);
      }

      // Store private data in KV (expires after 180 days to allow for delayed payouts)
      if (Object.keys(privateData).length > 0) {
        privateData.submissionId = submissionId;
        privateData.submitterId = submitterId;
        privateData.submittedAt = new Date().toISOString();
        await env.PRIVATE_DATA.put(
          `submission:${submissionId}`,
          JSON.stringify(privateData),
          { expirationTtl: 180 * 24 * 60 * 60 } // 180 days
        );
      }

      // Create GitHub issue (include submitterId for activity tracking)
      const issueResult = await createGitHubIssue(env, publicData, submissionId, submitterId, isNewLocation);

      if (!issueResult.success) {
        return new Response(JSON.stringify({ error: 'Failed to create GitHub issue', details: issueResult.error }), {
          status: 500,
          headers: { 'Content-Type': 'application/json', ...corsHeaders }
        });
      }

      // Return success
      return new Response(JSON.stringify({
        success: true,
        submissionId: submissionId,
        issueNumber: issueResult.issueNumber,
        issueUrl: issueResult.issueUrl
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json', ...corsHeaders }
      });

    } catch (error) {
      console.error('Error processing webhook:', error);
      return new Response(JSON.stringify({ error: 'Internal server error', message: error.message }), {
        status: 500,
        headers: { 'Content-Type': 'application/json', ...corsHeaders }
      });
    }
  }
};

/**
 * Extract fields from form webhook payload
 * Supports multiple formats: flat object, fields array, or nested data object
 */
function extractFormFields(payload) {
  const formData = {};

  // Handle different payload formats
  // Support both the fields array format and the flat format

  if (payload.data && payload.data.fields) {
    // Array format: { data: { fields: [{ key: 'field_id', value: 'xxx' }, ...] } }
    for (const field of payload.data.fields) {
      const key = field.key || field.id || field.label;
      const mappedKey = FIELD_MAPPING[key] || key;
      if (mappedKey && field.value !== undefined && field.value !== null) {
        formData[mappedKey] = String(field.value).trim();
      }
    }
  } else if (payload.data) {
    // Flat format: { data: { field_id: 'value', ... } }
    for (const [key, value] of Object.entries(payload.data)) {
      const mappedKey = FIELD_MAPPING[key] || key;
      if (mappedKey && value !== undefined && value !== null) {
        formData[mappedKey] = String(value).trim();
      }
    }
  } else if (payload.fields) {
    // Direct fields format
    for (const field of payload.fields) {
      const key = field.key || field.id || field.label;
      const mappedKey = FIELD_MAPPING[key] || key;
      if (mappedKey && field.value !== undefined && field.value !== null) {
        formData[mappedKey] = String(field.value).trim();
      }
    }
  }

  return formData;
}

/**
 * Fetch valid location IDs from GitHub Pages (with caching)
 */
async function fetchValidLocationIds(env) {
  const now = Date.now();

  // Return cached data if still fresh
  if (locationIdCache.ids.size > 0 && (now - locationIdCache.lastFetched) < CACHE_TTL_MS) {
    return locationIdCache.ids;
  }

  try {
    // Fetch locations.csv from GitHub Pages
    const url = `https://${env.GITHUB_OWNER}.github.io/${env.GITHUB_REPO}/locations.csv`;
    const response = await fetch(url, {
      headers: { 'User-Agent': 'sats4berlin-worker/1.0' }
    });

    if (!response.ok) {
      console.error(`Failed to fetch locations.csv: ${response.status}`);
      return locationIdCache.ids; // Return stale cache on error
    }

    const csvText = await response.text();
    const ids = new Set();

    // Simple CSV parsing - extract location_id from first column
    const lines = csvText.split('\n');
    for (let i = 1; i < lines.length; i++) { // Skip header
      const line = lines[i].trim();
      if (line) {
        // location_id is the first column
        const match = line.match(/^(DE-BE-\d{5})/);
        if (match) {
          ids.add(match[1]);
        }
      }
    }

    // Update cache
    locationIdCache = { ids, lastFetched: now };
    console.log(`Loaded ${ids.size} valid location IDs`);
    return ids;
  } catch (error) {
    console.error('Error fetching location IDs:', error);
    return locationIdCache.ids; // Return stale cache on error
  }
}

/**
 * Generate a unique submission ID
 */
function generateSubmissionId() {
  const timestamp = Date.now().toString(36);
  const random = Math.random().toString(36).substring(2, 8);
  return `SUB-${timestamp}-${random}`.toUpperCase();
}

/**
 * Generate a consistent submitter ID from contact info
 * Uses SHA-256 hash truncated to 12 chars for privacy
 */
async function generateSubmitterId(contactString) {
  const encoder = new TextEncoder();
  const data = encoder.encode(contactString);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  return `USER-${hashHex.substring(0, 12).toUpperCase()}`;
}

/**
 * Create a GitHub issue with the public form data
 */
async function createGitHubIssue(env, publicData, submissionId, submitterId, isNewLocation) {
  const today = new Date().toISOString().slice(0, 10);

  let title, body, labels;

  if (isNewLocation) {
    // New location submission
    const name = publicData.name || 'Unbekannt';
    title = `Neuer Ort: ${name} – ${today}`;
    labels = ['pending', 'new-location'];
    body = formatNewLocationBody(publicData, submissionId, submitterId);
  } else {
    // Check submission
    const locationId = publicData.location_id || 'UNKNOWN';
    const isCritical = publicData.check_type === 'critical';
    title = isCritical
      ? `⚠️ Kritische Änderung: ${locationId} – ${today}`
      : `Check: ${locationId} – ${today}`;
    labels = isCritical
      ? ['pending', 'check', 'critical']
      : ['pending', 'check'];
    body = formatCheckBody(publicData, submissionId, submitterId);
  }

  const response = await fetch(`https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/issues`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
      'Accept': 'application/vnd.github+json',
      'Content-Type': 'application/json',
      'User-Agent': 'sats4berlin-worker/1.0',
      'X-GitHub-Api-Version': '2022-11-28'
    },
    body: JSON.stringify({
      title: title,
      body: body,
      labels: labels
    })
  });

  if (!response.ok) {
    const errorText = await response.text();
    return { success: false, error: `GitHub API error: ${response.status} - ${errorText}` };
  }

  const issue = await response.json();
  return {
    success: true,
    issueNumber: issue.number,
    issueUrl: issue.html_url
  };
}

/**
 * Format the issue body for a check submission
 */
function formatCheckBody(data, submissionId, submitterId) {
  const isCritical = data.check_type === 'critical' || data.check_type?.includes('Kritisch');
  const checkTypeText = isCritical
    ? '⚠️ Kritische Änderung – Ort nimmt kein Bitcoin mehr / geschlossen / umgezogen'
    : 'Normaler Check – Ort akzeptiert weiterhin Bitcoin';

  // Different proof sections for normal vs critical checks
  let proofsSection;
  if (isCritical) {
    proofsSection = `### Nachweise (Kritische Änderung)

### Beweis-Foto

${data.critical_evidence_url || '_nicht angegeben_'}

### Öffentlicher Post (optional)

${data.critical_post_url || '_nicht angegeben_'}`;
  } else {
    proofsSection = `### Nachweise

### 1. Öffentlicher Post (Social Media)

${data.public_post_url || '_nicht angegeben_'}

### 2. Kaufbeleg (Bon/Rechnung)

${data.receipt_proof_url || '_nicht angegeben_'}

### 3. Bitcoin-Zahlung

${data.payment_proof_url || '_nicht angegeben_'}

### 4. Foto vom Ort

${data.venue_photo_url || '_nicht angegeben_'}`;
  }

  const observationsLabel = isCritical ? 'Was ist passiert?' : 'Wie lief die Zahlung?';

  return `## Satoshis für Berlin – Check

**Submission ID:** \`${submissionId}\`
**Submitter ID:** \`${submitterId || 'unknown'}\`

---

### Location-ID

${data.location_id || '_nicht angegeben_'}

### Datum und Uhrzeit des Kaufs

${data.date_time || '_nicht angegeben_'}

### Art des Checks

${checkTypeText}

---

${proofsSection}

---

### ${observationsLabel}

${data.observations || '_keine Angabe_'}

### Änderungen am Eintrag nötig? (optional)

${data.suggested_updates || '_keine Angabe_'}

---

_Eingereicht via Webformular. Kontaktdaten wurden separat gespeichert._
`;
}

/**
 * Format the issue body for a new location submission
 */
function formatNewLocationBody(data, submissionId, submitterId) {
  return `## Satoshis für Berlin – Neuer Ort

**Submission ID:** \`${submissionId}\`
**Submitter ID:** \`${submitterId || 'unknown'}\`

---

### Name des Ortes

${data.name || '_nicht angegeben_'}

### Adresse

${data.address || '_nicht angegeben_'}

### Kategorie

${data.category || '_nicht angegeben_'}

### Website (optional)

${data.website || '_nicht angegeben_'}

### OpenStreetMap-Link (optional)

${data.osm_url || '_nicht angegeben_'}

---

### Datum und Uhrzeit des Kaufs

${data.date_time || '_nicht angegeben_'}

---

### Nachweise

### 1. Öffentlicher Post (Social Media)

${data.public_post_url || '_nicht angegeben_'}

### 2. Kaufbeleg (Bon/Rechnung)

${data.receipt_proof_url || '_nicht angegeben_'}

### 3. Bitcoin-Zahlung

${data.payment_proof_url || '_nicht angegeben_'}

### 4. Foto vom Ort

${data.venue_photo_url || '_nicht angegeben_'}

---

### Wie lief die Zahlung?

${data.notes || '_keine Angabe_'}

---

_Eingereicht via Webformular. Kontaktdaten wurden separat gespeichert._
`;
}
