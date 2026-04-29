/**
 * PayoutHistory Component
 *
 * Renders a table of payouts with color-coded status badges + icons.
 * Status icons:
 *   pending    → Clock (yellow)
 *   processing → Spinning loader (blue)
 *   completed  → Checkmark circle (green)
 *   failed     → X circle (red)
 */

import React from 'react'

const formatPaise = (paise) => {
  const rupees = (paise ?? 0) / 100
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
  }).format(rupees)
}

const formatDate = (iso) => {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-IN', {
    dateStyle: 'short',
    timeStyle: 'short',
  })
}

// ── Status icon components ────────────────────────────────────────────────

function IconClock({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  )
}

function IconSpinner({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ animation: 'spin 1.2s linear infinite' }}>
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  )
}

function IconCheckCircle({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  )
}

function IconXCircle({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="15" y1="9" x2="9" y2="15" />
      <line x1="9" y1="9" x2="15" y2="15" />
    </svg>
  )
}

// ── Status badge config ───────────────────────────────────────────────────

const STATUS_CONFIG = {
  pending: {
    badge: 'badge-pending',
    Icon: IconClock,
    label: 'Pending',
  },
  processing: {
    badge: 'badge-processing',
    Icon: IconSpinner,
    label: 'Processing',
  },
  completed: {
    badge: 'badge-completed',
    Icon: IconCheckCircle,
    label: 'Completed',
  },
  failed: {
    badge: 'badge-failed',
    Icon: IconXCircle,
    label: 'Failed',
  },
}

function StatusBadge({ status }) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending
  const { badge, Icon, label } = config

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${badge}`}>
      <Icon className="w-3.5 h-3.5 flex-shrink-0" />
      {label}
    </span>
  )
}

// ── Main component ────────────────────────────────────────────────────────

export default function PayoutHistory({ payouts }) {
  if (!payouts || payouts.length === 0) {
    return (
      <div className="glass p-6">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-widest mb-4">
          Payout History
        </h2>
        <p className="text-slate-500 text-sm">No payouts yet. Submit your first payout above.</p>
      </div>
    )
  }

  return (
    <div className="glass p-6">
      {/* Inject spin keyframe once */}
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>

      <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-widest mb-4">
        Payout History
      </h2>

      <div className="overflow-x-auto">
        <table className="w-full text-sm" id="payout-history-table">
          <thead>
            <tr className="border-b border-white/[0.06]">
              {['ID', 'Amount', 'Status', 'Attempts', 'Created', 'Updated'].map((h) => (
                <th
                  key={h}
                  className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {payouts.map((p) => (
              <tr
                key={p.id}
                className="border-b border-white/[0.03] hover:bg-white/[0.03] transition-colors"
              >
                <td className="py-3 px-3 text-slate-400 font-mono">#{p.id}</td>
                <td className="py-3 px-3 text-slate-200 font-semibold">{formatPaise(p.amount_paise)}</td>
                <td className="py-3 px-3">
                  <StatusBadge status={p.status} />
                </td>
                <td className="py-3 px-3 text-slate-400">{p.attempts}</td>
                <td className="py-3 px-3 text-slate-500 text-xs">{formatDate(p.created_at)}</td>
                <td className="py-3 px-3 text-slate-500 text-xs">{formatDate(p.updated_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
