/**
 * Dashboard Component
 *
 * Displays available balance, held balance, and a sparkline-style
 * transaction list. Receives data from parent (App.jsx) via props
 * and re-renders on every poll cycle.
 */

import React from 'react'

const formatPaise = (paise) => {
  if (paise == null) return '—'
  const rupees = paise / 100
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
  }).format(rupees)
}

const formatDate = (iso) => {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

export default function Dashboard({ data, loading }) {
  if (loading && !data) {
    return (
      <div className="flex items-center justify-center h-40">
        <div className="w-8 h-8 rounded-full border-2 border-brand-400 border-t-transparent animate-spin" />
      </div>
    )
  }

  const available = data?.available_balance ?? 0
  const held = data?.held_balance ?? 0
  const transactions = data?.transactions ?? []

  return (
    <div className="space-y-6">
      {/* Balance Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Available */}
        <div className="glass p-6 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-sky-500/10 to-indigo-600/5 pointer-events-none rounded-2xl" />
          <p className="text-xs font-medium text-slate-400 uppercase tracking-widest mb-1">
            Available Balance
          </p>
          <p className="text-3xl font-bold gradient-text">{formatPaise(available)}</p>
          <p className="text-xs text-slate-500 mt-2">Ready to withdraw</p>
        </div>

        {/* Held */}
        <div className="glass p-6 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-amber-500/10 to-orange-600/5 pointer-events-none rounded-2xl" />
          <p className="text-xs font-medium text-slate-400 uppercase tracking-widest mb-1">
            Held Balance
          </p>
          <p className="text-3xl font-bold text-amber-400">{formatPaise(held)}</p>
          <p className="text-xs text-slate-500 mt-2">Pending &amp; processing payouts</p>
        </div>
      </div>

      {/* Recent Transactions */}
      <div className="glass p-6">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-widest mb-4">
          Recent Transactions
        </h2>
        {transactions.length === 0 ? (
          <p className="text-slate-500 text-sm">No transactions yet.</p>
        ) : (
          <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
            {transactions.map((tx) => (
              <div
                key={tx.id}
                className="flex items-center justify-between py-2 px-3 rounded-lg bg-white/[0.03] hover:bg-white/[0.06] transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      tx.type === 'CREDIT' ? 'bg-emerald-400' : 'bg-rose-400'
                    }`}
                  />
                  <div>
                    <p className="text-sm font-medium text-slate-200">
                      {tx.reference || tx.type}
                    </p>
                    <p className="text-xs text-slate-500">{formatDate(tx.created_at)}</p>
                  </div>
                </div>
                <span
                  className={`text-sm font-semibold ${
                    tx.type === 'CREDIT' ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {tx.type === 'CREDIT' ? '+' : '-'}
                  {formatPaise(tx.amount_paise)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
