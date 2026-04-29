/**
 * PayoutForm Component
 *
 * Submits a payout request to POST /api/v1/payouts.
 * Generates a UUID idempotency key client-side for each new submission.
 * On retry of the same form data, keep the same key (stored in state).
 */

import React, { useState } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { createPayout } from '../api/client'

export default function PayoutForm({ merchantId, onSuccess }) {
  const [amountRupees, setAmountRupees] = useState('')
  const [bankAccountId, setBankAccountId] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  // Each form submission gets a fresh UUID; cleared on success
  const [idempotencyKey] = useState(() => uuidv4())

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setSuccess(null)

    const amount = parseFloat(amountRupees)
    if (!amountRupees || isNaN(amount) || amount <= 0) {
      setError('Enter a valid amount greater than 0.')
      return
    }
    if (!bankAccountId.trim()) {
      setError('Bank account ID is required.')
      return
    }

    const amountPaise = Math.round(amount * 100)

    setLoading(true)
    try {
      const result = await createPayout(
        merchantId,
        amountPaise,
        bankAccountId.trim(),
        idempotencyKey,
      )
      setSuccess(`Payout #${result.id} created — status: ${result.status}`)
      setAmountRupees('')
      setBankAccountId('')
      if (onSuccess) onSuccess()
    } catch (err) {
      const msg =
        err.response?.data?.error ||
        err.response?.data?.amount_paise?.[0] ||
        'Something went wrong. Please try again.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="glass p-6">
      <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-widest mb-6">
        Request Payout
      </h2>

      <form onSubmit={handleSubmit} className="space-y-4" id="payout-form">
        {/* Amount */}
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1.5" htmlFor="payout-amount">
            Amount (₹)
          </label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-medium">₹</span>
            <input
              id="payout-amount"
              type="number"
              min="0.01"
              step="0.01"
              value={amountRupees}
              onChange={(e) => setAmountRupees(e.target.value)}
              placeholder="0.00"
              className="w-full pl-8 pr-4 py-2.5 rounded-lg bg-white/[0.05] border border-white/[0.08]
                         text-slate-100 placeholder-slate-600 text-sm
                         focus:outline-none focus:ring-2 focus:ring-brand-400/50 focus:border-brand-400/50
                         transition-all"
            />
          </div>
        </div>

        {/* Bank Account ID */}
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1.5" htmlFor="payout-bank">
            Bank Account ID
          </label>
          <input
            id="payout-bank"
            type="text"
            value={bankAccountId}
            onChange={(e) => setBankAccountId(e.target.value)}
            placeholder="e.g. HDFC_0012345678"
            className="w-full px-4 py-2.5 rounded-lg bg-white/[0.05] border border-white/[0.08]
                       text-slate-100 placeholder-slate-600 text-sm
                       focus:outline-none focus:ring-2 focus:ring-brand-400/50 focus:border-brand-400/50
                       transition-all"
          />
        </div>

        {/* Idempotency Key (read-only info) */}
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1.5">
            Idempotency Key (auto-generated)
          </label>
          <p className="text-xs text-slate-600 font-mono bg-white/[0.03] px-3 py-2 rounded-lg border border-white/[0.05] break-all">
            {idempotencyKey}
          </p>
        </div>

        {/* Error / Success */}
        {error && (
          <div className="px-4 py-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm">
            {error}
          </div>
        )}
        {success && (
          <div className="px-4 py-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm">
            {success}
          </div>
        )}

        {/* Submit */}
        <button
          id="payout-submit"
          type="submit"
          disabled={loading || !merchantId}
          className="w-full py-2.5 rounded-lg font-semibold text-sm
                     bg-gradient-to-r from-sky-500 to-indigo-500
                     hover:from-sky-400 hover:to-indigo-400
                     disabled:opacity-40 disabled:cursor-not-allowed
                     transition-all duration-200 text-white shadow-lg shadow-sky-500/20"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
              Processing…
            </span>
          ) : 'Submit Payout'}
        </button>
      </form>
    </div>
  )
}
