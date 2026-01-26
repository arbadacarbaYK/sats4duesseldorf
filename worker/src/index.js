/**
 * sats4berlin Form Handler
 *
 * Receives form submissions, creates GitHub issues with public data,
 * and stores private contact information in Cloudflare KV.
 */

import { handleAdminRequest } from './admin.js';

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
const CHECK_REQUIRED_FIELDS = ['location_id', 'date_time', 'public_post_url'];
const NEW_LOCATION_REQUIRED_FIELDS = ['name', 'address', 'category'];

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
    if (url.pathname !== '/webhook/tally') {
      return new Response('Not found', { status: 404 });
    }

    // Only accept POST requests for webhook
    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405 });
    }

    try {
      // Parse the webhook payload
      const payload = await request.json();

      // Extract form data from the payload
      const formData = extractFormFields(payload);

      if (!formData || Object.keys(formData).length === 0) {
        return new Response(JSON.stringify({ error: 'No form data found' }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' }
        });
      }

      // Determine form type
      const isNewLocation = NEW_LOCATION_REQUIRED_FIELDS.every(f => formData[f]);
      const isCheck = CHECK_REQUIRED_FIELDS.every(f => formData[f]);

      if (!isNewLocation && !isCheck) {
        return new Response(JSON.stringify({ error: 'Invalid form data - missing required fields' }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' }
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

      // Store private data in KV (expires after 90 days)
      if (Object.keys(privateData).length > 0) {
        privateData.submissionId = submissionId;
        privateData.submitterId = submitterId;
        privateData.submittedAt = new Date().toISOString();
        await env.PRIVATE_DATA.put(
          `submission:${submissionId}`,
          JSON.stringify(privateData),
          { expirationTtl: 90 * 24 * 60 * 60 } // 90 days
        );
      }

      // Create GitHub issue (include submitterId for activity tracking)
      const issueResult = await createGitHubIssue(env, publicData, submissionId, submitterId, isNewLocation);

      if (!issueResult.success) {
        return new Response(JSON.stringify({ error: 'Failed to create GitHub issue', details: issueResult.error }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' }
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
        headers: { 'Content-Type': 'application/json' }
      });

    } catch (error) {
      console.error('Error processing webhook:', error);
      return new Response(JSON.stringify({ error: 'Internal server error', message: error.message }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
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
    title = `Check: ${locationId} – ${today}`;
    labels = ['pending', 'check'];
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
  const checkTypeText = data.check_type === 'critical' || data.check_type?.includes('Kritisch')
    ? 'Kritische Änderung – Ort nimmt kein Bitcoin mehr / geschlossen / umgezogen'
    : 'Normaler Check – Ort akzeptiert weiterhin Bitcoin';

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
