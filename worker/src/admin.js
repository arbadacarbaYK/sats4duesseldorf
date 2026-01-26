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

  // Verify admin authentication
  const authHeader = request.headers.get('Authorization');
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const token = authHeader.substring(7);
  // Use timing-safe comparison to prevent timing attacks
  if (!timingSafeEqual(token, env.ADMIN_API_TOKEN || '')) {
    return new Response(JSON.stringify({ error: 'Invalid token' }), {
      status: 403,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Route admin requests
  if (url.pathname === '/admin/contact' && request.method === 'GET') {
    return await getContactInfo(url, env);
  }

  if (url.pathname === '/admin/mark-paid' && request.method === 'POST') {
    return await markAsPaid(request, env);
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
async function getContactInfo(url, env) {
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
    return new Response(JSON.stringify({ error: 'Submission not found or expired' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  return new Response(data, {
    status: 200,
    headers: { 'Content-Type': 'application/json' }
  });
}

/**
 * Mark a submission as paid and optionally delete contact info
 * POST /admin/mark-paid { submission_id: 'SUB-XXXXX', delete_data: true }
 */
async function markAsPaid(request, env) {
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
    return new Response(JSON.stringify({ success: true, message: 'Marked as paid' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}
