/**
 * Admin API for retrieving private contact information
 *
 * This module provides endpoints for maintainers to access
 * private payout details after a submission is approved.
 *
 * Note: This is meant to be integrated into the main worker
 * or deployed as a separate protected endpoint.
 */

// Submission ID format validation
const SUBMISSION_ID_REGEX = /^SUB-[A-Z0-9]+-[A-Z0-9]+$/;

// Allowed origins for admin API (more restrictive than webhook)
// Only allow from the main GitHub Pages site, no localhost
const ADMIN_ALLOWED_ORIGINS = [
  'https://satoshiinberlin.github.io',
];

/**
 * Log admin action for audit trail
 */
async function logAdminAction(env, action, details, clientIP) {
  const logEntry = {
    timestamp: new Date().toISOString(),
    action,
    details,
    clientIP: clientIP || 'unknown',
  };

  // Store audit log with 1 year expiration
  const logKey = `audit:${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;
  try {
    await env.PRIVATE_DATA.put(logKey, JSON.stringify(logEntry), {
      expirationTtl: 365 * 24 * 60 * 60
    });
  } catch (e) {
    console.error('Failed to write audit log:', e);
  }
}

/**
 * Timing-safe string comparison to prevent timing attacks
 */
function timingSafeEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') {
    return false;
  }
  if (a.length !== b.length) {
    // Still do comparison to maintain constant time for same-length strings
    // But we know it will fail
    b = a;
  }
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return result === 0 && a.length === b.length;
}

/**
 * Handle admin API requests
 * @param {Request} request
 * @param {Env} env
 * @returns {Response}
 */
export async function handleAdminRequest(request, env) {
  const url = new URL(request.url);
  const clientIP = request.headers.get('CF-Connecting-IP') || 'unknown';

  // Validate Origin header for CSRF protection
  const origin = request.headers.get('Origin');
  // Allow dev origins if ADMIN_ALLOWED_ORIGINS_DEV is set (comma-separated)
  const devOrigins = env.ADMIN_ALLOWED_ORIGINS_DEV ? env.ADMIN_ALLOWED_ORIGINS_DEV.split(',') : [];
  const allAllowedOrigins = [...ADMIN_ALLOWED_ORIGINS, ...devOrigins];

  if (origin && !allAllowedOrigins.some(allowed => origin.startsWith(allowed.trim()))) {
    await logAdminAction(env, 'BLOCKED_ORIGIN', { origin, path: url.pathname }, clientIP);
    return new Response(JSON.stringify({ error: 'Invalid origin' }), {
      status: 403,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Verify admin authentication
  const authHeader = request.headers.get('Authorization');
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    await logAdminAction(env, 'AUTH_MISSING', { path: url.pathname }, clientIP);
    return new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const token = authHeader.substring(7);

  // Validate token - use same error response for all failure modes to prevent information leakage
  // This includes: missing config, short config, wrong token
  const isConfigValid = env.ADMIN_API_TOKEN && env.ADMIN_API_TOKEN.length >= 16;
  const isTokenValid = isConfigValid && timingSafeEqual(token, env.ADMIN_API_TOKEN);

  if (!isTokenValid) {
    // Log internally but don't reveal which check failed
    if (!isConfigValid) {
      console.error('ADMIN_API_TOKEN is not configured or too short');
    }
    await logAdminAction(env, 'AUTH_FAILED', { path: url.pathname }, clientIP);
    return new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Route admin requests
  if (url.pathname === '/admin/contact' && request.method === 'GET') {
    return await getContactInfo(url, env, clientIP);
  }

  if (url.pathname === '/admin/mark-paid' && request.method === 'POST') {
    return await markAsPaid(request, env, clientIP);
  }

  return new Response(JSON.stringify({ error: 'Not found' }), {
    status: 404,
    headers: { 'Content-Type': 'application/json' }
  });
}

/**
 * Get contact info for a submission
 * GET /admin/contact?submission_id=SUB-XXXXX
 */
async function getContactInfo(url, env, clientIP) {
  const submissionId = url.searchParams.get('submission_id');

  if (!submissionId) {
    return new Response(JSON.stringify({ error: 'Missing submission_id parameter' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Validate submission ID format to prevent KV key injection
  if (!SUBMISSION_ID_REGEX.test(submissionId)) {
    return new Response(JSON.stringify({ error: 'Invalid submission_id format' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const data = await env.PRIVATE_DATA.get(`submission:${submissionId}`);

  if (!data) {
    await logAdminAction(env, 'CONTACT_NOT_FOUND', { submissionId }, clientIP);
    return new Response(JSON.stringify({ error: 'Submission not found or expired' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Log successful access to contact info
  await logAdminAction(env, 'CONTACT_ACCESSED', { submissionId }, clientIP);

  return new Response(data, {
    status: 200,
    headers: { 'Content-Type': 'application/json' }
  });
}

/**
 * Mark a submission as paid and optionally delete contact info
 * POST /admin/mark-paid { submission_id: 'SUB-XXXXX', delete_data: true }
 */
async function markAsPaid(request, env, clientIP) {
  let body;
  try {
    body = await request.json();
  } catch {
    return new Response(JSON.stringify({ error: 'Invalid JSON body' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const submissionId = body.submission_id;

  if (!submissionId) {
    return new Response(JSON.stringify({ error: 'Missing submission_id' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Validate submission ID format to prevent KV key injection
  if (!SUBMISSION_ID_REGEX.test(submissionId)) {
    return new Response(JSON.stringify({ error: 'Invalid submission_id format' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Get existing data
  const data = await env.PRIVATE_DATA.get(`submission:${submissionId}`);

  if (!data) {
    await logAdminAction(env, 'MARK_PAID_NOT_FOUND', { submissionId }, clientIP);
    return new Response(JSON.stringify({ error: 'Submission not found' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const parsed = JSON.parse(data);
  parsed.paidAt = new Date().toISOString();
  parsed.paid = true;

  if (body.delete_data) {
    // Delete private data after payment
    await env.PRIVATE_DATA.delete(`submission:${submissionId}`);
    await logAdminAction(env, 'MARKED_PAID_DELETED', { submissionId }, clientIP);
    return new Response(JSON.stringify({ success: true, message: 'Marked as paid and data deleted' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } else {
    // Update with paid status
    await env.PRIVATE_DATA.put(
      `submission:${submissionId}`,
      JSON.stringify(parsed),
      { expirationTtl: 30 * 24 * 60 * 60 } // Keep for 30 more days
    );
    await logAdminAction(env, 'MARKED_PAID', { submissionId }, clientIP);
    return new Response(JSON.stringify({ success: true, message: 'Marked as paid' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}
