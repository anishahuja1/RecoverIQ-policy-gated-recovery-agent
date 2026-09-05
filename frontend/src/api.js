/**
 * RecoverIQ API Client
 * All backend communication is centralized here.
 * Falls back gracefully if backend is unavailable.
 *
 * LOCAL DEV:  BASE is empty string — Vite proxy forwards /api to localhost:8000
 * PRODUCTION: Set VITE_API_URL in Vercel to your deployed backend URL.
 *             e.g. VITE_API_URL=https://recoveriq-api.onrender.com
 */

const BASE = import.meta.env.VITE_API_URL || '';

export async function fetchHealth() {
  const res = await fetch(`${BASE}/health`);
  if (!res.ok) throw new Error('Backend unavailable');
  return res.json();
}

export async function seedPayments() {
  const res = await fetch(`${BASE}/api/seed`, { method: 'POST' });
  if (!res.ok) throw new Error('Seed failed');
  return res.json();
}

export async function runBatch() {
  const res = await fetch(`${BASE}/api/run-batch`, { method: 'POST' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Batch run failed');
  }
  return res.json();
}

export async function fetchPayments(status = null) {
  const url = status
    ? `${BASE}/api/payments?status=${encodeURIComponent(status)}`
    : `${BASE}/api/payments`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch payments');
  return res.json();
}

export async function fetchPaymentAudit(paymentId) {
  const res = await fetch(`${BASE}/api/payments/${paymentId}/audit`);
  if (!res.ok) throw new Error('Failed to fetch audit log');
  return res.json();
}

export async function fetchMetrics() {
  const res = await fetch(`${BASE}/api/metrics`);
  if (!res.ok) throw new Error('Failed to fetch metrics');
  return res.json();
}

export async function fetchAudioSample() {
  const res = await fetch(`${BASE}/api/audio-sample`);
  if (!res.ok) throw new Error('Failed to fetch audio sample');
  return res.json();
}
