/**
 * Axios API client.
 *
 * Local dev  → baseURL is '' so Vite proxy forwards /api → localhost:8000
 * Production → set VITE_API_BASE_URL=https://your-app.onrender.com in Vercel
 */

import axios from 'axios'

const api = axios.create({
  baseURL: (import.meta.env.VITE_API_BASE_URL ?? '') + '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// ── Merchants ──────────────────────────────────────────────────────────────

export const fetchMerchants = () => api.get('/merchants').then(r => r.data)

// ── Dashboard ──────────────────────────────────────────────────────────────

export const fetchDashboard = (merchantId) =>
  api.get('/dashboard', { params: { merchant_id: merchantId } }).then(r => r.data)

// ── Payouts ────────────────────────────────────────────────────────────────

/**
 * Create a payout.
 * @param {number} merchantId
 * @param {number} amountPaise
 * @param {string} bankAccountId
 * @param {string} idempotencyKey  UUID string generated client-side
 */
export const createPayout = (merchantId, amountPaise, bankAccountId, idempotencyKey) =>
  api.post(
    '/payouts',
    { amount_paise: amountPaise, bank_account_id: bankAccountId },
    {
      params: { merchant_id: merchantId },
      headers: { 'Idempotency-Key': idempotencyKey },
    }
  ).then(r => r.data)
