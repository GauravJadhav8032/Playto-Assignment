/**
 * App — root component and application shell.
 *
 * Responsibilities:
 *  - Load merchant list once on mount
 *  - Let user select active merchant via dropdown
 *  - Poll GET /dashboard every 4 seconds while a merchant is selected
 *  - Pass data down to child components (no prop drilling beyond one level)
 */

import React, { useState, useEffect, useCallback, useRef } from 'react'
import { fetchMerchants, fetchDashboard } from './api/client'
import Dashboard from './components/Dashboard'
import PayoutForm from './components/PayoutForm'
import PayoutHistory from './components/PayoutHistory'

const POLL_INTERVAL_MS = 4000

export default function App() {
  const [merchants, setMerchants] = useState([])
  const [selectedMerchantId, setSelectedMerchantId] = useState(null)
  const [dashboardData, setDashboardData] = useState(null)
  const [loadingDashboard, setLoadingDashboard] = useState(false)
  const [dashboardError, setDashboardError] = useState(null)
  const pollRef = useRef(null)

  // ── Load merchants once ────────────────────────────────────────────────
  useEffect(() => {
    fetchMerchants()
      .then((data) => {
        setMerchants(data)
        if (data.length > 0) setSelectedMerchantId(data[0].id)
      })
      .catch(() => setDashboardError('Failed to load merchants. Is the backend running?'))
  }, [])

  // ── Fetch dashboard (also used as manual refresh after payout) ─────────
  const refreshDashboard = useCallback(async (merchantId) => {
    if (!merchantId) return
    setLoadingDashboard(true)
    try {
      const data = await fetchDashboard(merchantId)
      setDashboardData(data)
      setDashboardError(null)
    } catch {
      setDashboardError('Failed to fetch dashboard data.')
    } finally {
      setLoadingDashboard(false)
    }
  }, [])

  // ── Poll on merchant change ────────────────────────────────────────────
  useEffect(() => {
    if (!selectedMerchantId) return

    // Immediate fetch
    refreshDashboard(selectedMerchantId)

    // Set up polling
    pollRef.current = setInterval(
      () => refreshDashboard(selectedMerchantId),
      POLL_INTERVAL_MS
    )

    return () => clearInterval(pollRef.current)
  }, [selectedMerchantId, refreshDashboard])

  // ── Selected merchant name ─────────────────────────────────────────────
  const selectedMerchant = merchants.find((m) => m.id === selectedMerchantId)

  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Header ── */}
      <header className="glass border-b border-white/[0.06] px-6 py-4 flex items-center justify-between sticky top-0 z-30" style={{borderRadius: 0}}>
        <div className="flex items-center gap-3">
          {/* Live indicator */}
          <span className="relative w-2.5 h-2.5 flex-shrink-0">
            <span className="pulse-dot relative block w-2.5 h-2.5 rounded-full bg-emerald-400" />
          </span>
          <h1 className="text-lg font-bold gradient-text tracking-tight">
            Payout Engine
          </h1>
          <span className="text-xs text-slate-600 hidden sm:block">by Playto</span>
        </div>

        {/* Merchant selector */}
        <div className="flex items-center gap-3">
          <label htmlFor="merchant-select" className="text-xs text-slate-500 font-medium">
            Merchant:
          </label>
          <select
            id="merchant-select"
            value={selectedMerchantId ?? ''}
            onChange={(e) => {
              setDashboardData(null)
              setSelectedMerchantId(Number(e.target.value))
            }}
            className="bg-white/[0.05] border border-white/[0.08] text-slate-200 text-sm
                       rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-400/40
                       cursor-pointer"
          >
            {merchants.map((m) => (
              <option key={m.id} value={m.id} className="bg-slate-900">
                {m.name}
              </option>
            ))}
          </select>
        </div>
      </header>

      {/* ── Main ── */}
      <main className="flex-1 max-w-5xl mx-auto w-full px-4 sm:px-6 py-8 space-y-6">
        {/* Error banner */}
        {dashboardError && (
          <div className="px-5 py-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm">
            ⚠ {dashboardError}
          </div>
        )}

        {/* Top row: dashboard stats + payout form */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          <div className="lg:col-span-3">
            <Dashboard data={dashboardData} loading={loadingDashboard} />
          </div>
          <div className="lg:col-span-2">
            <PayoutForm
              merchantId={selectedMerchantId}
              onSuccess={() => refreshDashboard(selectedMerchantId)}
            />
          </div>
        </div>

        {/* Payout history table */}
        <PayoutHistory payouts={dashboardData?.payouts ?? []} />

        {/* Poll indicator */}
        <p className="text-center text-xs text-slate-700">
          Auto-refreshing every {POLL_INTERVAL_MS / 1000}s
          {selectedMerchant ? ` · ${selectedMerchant.name}` : ''}
        </p>
      </main>
    </div>
  )
}
