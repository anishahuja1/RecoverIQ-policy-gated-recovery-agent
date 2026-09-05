import React, { useState, useEffect, useCallback } from 'react'
import {
  runBatch, fetchPayments, fetchMetrics, fetchPaymentAudit, fetchAudioSample, fetchHealth
} from './api.js'

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(amount) {
  if (amount == null) return '—'
  return '₹' + Number(amount).toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

function fmtFull(amount) {
  if (amount == null) return '—'
  return '₹' + Number(amount).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function cap(s) {
  if (!s) return '—'
  return s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, ' ')
}

const FAILURE_LABELS = {
  soft_decline: 'Soft Decline',
  insufficient_funds: 'Insufficient Funds',
  hard_decline: 'Hard Decline',
  authentication_failed: 'Auth Failed',
  checkout_abandoned: 'Checkout Abandoned',
  subscription_failed: 'Subscription Failed',
}

const ACTOR_LABELS = {
  system: 'System',
  diagnosis_engine: 'Diagnosis Engine',
  policy_engine: 'Policy Engine',
  recovery_executor: 'Recovery Executor',
  baseline_simulator: 'Baseline Simulator',
}

const FILTERS = [
  { label: 'All', value: null },
  { label: 'Recovered', value: 'recovered' },
  { label: 'Not Recovered', value: 'not_recovered' },
  { label: 'Blocked', value: 'blocked' },
  { label: 'Escalated', value: 'escalated' },
  { label: 'Needs Customer Action', value: 'needs_customer_action' },
]

// ── Sub-components ────────────────────────────────────────────────────────────

function MetricCard({ label, value, sub, color, extra }) {
  return (
    <div className={`metric-card ${color || ''}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value ?? '—'}</div>
      {sub && <div className="metric-sub">{sub}</div>}
      {extra}
    </div>
  )
}

function PolicyBadge({ decision }) {
  if (!decision) return <span className="text-muted">—</span>
  return (
    <span className={`policy-badge policy-${decision}`}>
      {decision === 'approved' && '✓ '}
      {decision === 'modified' && '~ '}
      {decision === 'blocked' && '✗ '}
      {decision === 'escalated' && '⚠ '}
      {cap(decision)}
    </span>
  )
}

function StatusBadge({ status }) {
  if (!status || status === 'pending') return <span className="status-badge status-pending">Pending</span>
  const icons = {
    recovered: '✓',
    not_recovered: '✗',
    blocked: '⊘',
    escalated: '⚠',
    needs_customer_action: '→',
    unresolved: '?',
  }
  return (
    <span className={`status-badge status-${status}`}>
      {icons[status] || ''} {cap(status)}
    </span>
  )
}

function AuditTrail({ paymentId, batchRan }) {
  const [entries, setEntries] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!batchRan) { setLoading(false); return }
    setLoading(true)
    fetchPaymentAudit(paymentId)
      .then(data => { setEntries(data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [paymentId, batchRan])

  if (loading) return <div className="audit-loading">Loading audit trail…</div>
  if (error) return <div className="audit-loading" style={{ color: '#dc2626' }}>Error: {error}</div>
  if (!entries || entries.length === 0) return (
    <div className="audit-loading">No audit entries yet. Click "Run Recovery Batch" to generate the audit trail.</div>
  )

  return (
    <div className="audit-timeline">
      {entries.map((e, i) => (
        <div key={e.id || i} className="audit-entry">
          <div className={`audit-dot ${e.actor}`} />
          <div className="audit-content">
            <div className="audit-header">
              <span className="audit-actor">{ACTOR_LABELS[e.actor] || e.actor}</span>
              <span className="audit-event">{e.event_type}</span>
              <span className="audit-time">{fmtTime(e.timestamp)}</span>
            </div>
            <div className="audit-message">{e.message}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

function PaymentRow({ payment, batchRan, expanded, onToggle }) {
  const colCount = 9

  return (
    <>
      <tr className={expanded ? 'expanded' : ''}>
        <td>
          <div className="payment-id">{payment.payment_id}</div>
          <div className="text-sm text-muted">{payment.customer_name}</div>
        </td>
        <td>
          <div className="amount">{fmt(payment.amount)}</div>
          <div className="text-sm text-muted mono">{payment.currency} · {payment.payment_method}</div>
        </td>
        <td>
          <span className={`failure-badge failure-${payment.failure_category}`}>
            {FAILURE_LABELS[payment.failure_category] || cap(payment.failure_category)}
          </span>
          <div className="text-sm text-muted mono" style={{ marginTop: 3, fontSize: 10 }}>
            {payment.failure_code}
          </div>
        </td>
        <td>
          {payment.ai_diagnosis ? (
            <div className="diagnosis-cell">
              <div>{cap(payment.ai_diagnosis)}</div>
              <div className="confidence">
                conf: {payment.ai_confidence != null ? (payment.ai_confidence * 100).toFixed(0) + '%' : '—'}
                {' · '}{payment.ai_risk_level || '—'}
              </div>
            </div>
          ) : <span className="text-muted">—</span>}
        </td>
        <td><PolicyBadge decision={payment.policy_decision} /></td>
        <td>
          {payment.action_taken
            ? <span className="action-cell mono">{payment.action_taken}</span>
            : <span className="text-muted">—</span>}
        </td>
        <td><StatusBadge status={payment.final_status} /></td>
        <td>
          {payment.recovered_amount > 0
            ? <span className="recovered-amount">{fmtFull(payment.recovered_amount)}</span>
            : <span className="recovered-amount zero">₹0</span>}
        </td>
        <td>
          <button
            id={`audit-btn-${payment.payment_id}`}
            className={`audit-btn ${expanded ? 'open' : ''}`}
            onClick={() => onToggle(payment.payment_id)}
            title="View audit trail"
          >
            {expanded ? '▲' : '▼'} Audit
          </button>
        </td>
      </tr>
      {expanded && (
        <tr className="audit-row">
          <td colSpan={colCount}>
            <div className="audit-trail">
              <div className="audit-trail-title">
                📋 Audit Trail — {payment.payment_id}
                {payment.policy_idempotency_key && (
                  <span className="text-sm text-muted mono" style={{ fontWeight: 400, marginLeft: 8 }}>
                    key: {payment.policy_idempotency_key}
                  </span>
                )}
              </div>
              <AuditTrail paymentId={payment.payment_id} batchRan={batchRan} />
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function AudioCard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchAudioSample()
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  if (loading) return null

  return (
    <div className="audio-section">
      <div className="section-header">
        <div>
          <div className="section-title">Voice Recovery Nudge (Demo)</div>
          <div className="section-sub">Hinglish outbound reminder — cached demo, not a real phone call</div>
        </div>
      </div>
      <div className="audio-card">
        <div className="audio-card-header">
          <div className="audio-icon">🎙</div>
          <div>
            <div className="audio-card-title">{data?.title || 'Hinglish Recovery Nudge'}</div>
            <div className="audio-card-subtitle">
              {data?.language || 'Hinglish'} · {data?.duration_seconds || 14}s · Demo mode
            </div>
          </div>
          <span className="audio-disclaimer">
            ⚠ Cached demo — not a real call
          </span>
        </div>
        <div className="audio-card-body">
          <div className="audio-left">
            <div className="audio-meta">
              <strong>Case Context</strong><br />
              {data?.case_context || 'pay_AF001 · Rahul Sharma · ₹2,499 · 3DS Failed · hi-IN'}
            </div>
            <div className="audio-player-label">Audio Player</div>
            <div className="audio-player-area">
              <div style={{ width: '100%' }}>
                <audio controls preload="none" id="demo-audio-player">
                  <source src="/demo-audio.wav" type="audio/wav" />
                  Your browser does not support the audio element.
                </audio>
                <div className="audio-no-file">
                  ℹ No audio file bundled. In a production demo, a pre-recorded Hinglish nudge would play here.
                </div>
              </div>
            </div>
          </div>
          <div className="audio-right">
            <div className="transcript-label">Transcript (Hinglish)</div>
            <div className="transcript-text">
              {data?.transcript ||
                'Hi Rahul, aapka ₹2,499 ka payment complete nahi ho paya kyunki bank authentication fail ho gaya. Aap secure payment link se payment dobara complete kar sakte hain. Yeh reminder sirf ek baar bheja gaya hai. Dhanyavaad.'}
            </div>
            <div style={{ marginTop: 12, padding: '10px 12px', background: '#fef9c3', border: '1px solid #fde68a', borderRadius: 6, fontSize: 11, color: '#92400e', lineHeight: 1.6 }}>
              <strong>⚠ Disclaimer:</strong> {data?.disclaimer ||
                'This is a cached demo nudge. No real phone call was made. No real message was sent. Voice reminders in production require explicit customer consent and a compliant telephony API.'}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Main App ──────────────────────────────────────────────────────────────────

export default function App() {
  const [health, setHealth] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [payments, setPayments] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [batchRan, setBatchRan] = useState(false)
  const [expandedRow, setExpandedRow] = useState(null)
  const [activeFilter, setActiveFilter] = useState(null)
  const [mode, setMode] = useState('DEMO_MODE')

  // Check health on mount
  useEffect(() => {
    fetchHealth()
      .then(h => { setHealth(h); setMode(h.mode || 'DEMO_MODE') })
      .catch(() => setHealth(null))

    // Load any pre-existing payments
    fetchPayments()
      .then(p => {
        if (p && p.length > 0) {
          setPayments(p)
          const hasResults = p.some(x => x.final_status)
          if (hasResults) {
            setBatchRan(true)
            fetchMetrics().then(setMetrics).catch(() => {})
          }
        }
      })
      .catch(() => {})
  }, [])

  const handleRunBatch = useCallback(async () => {
    setLoading(true)
    setError(null)
    setExpandedRow(null)
    try {
      const result = await runBatch()
      setPayments(result.payments || [])
      setMetrics(result.metrics || null)
      setMode(result.mode || 'DEMO_MODE')
      setBatchRan(true)
    } catch (e) {
      setError(e.message || 'Failed to run batch. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }, [])

  const toggleRow = useCallback((id) => {
    setExpandedRow(prev => prev === id ? null : id)
  }, [])

  // Filter payments client-side (fast, avoids extra round-trips)
  const filteredPayments = activeFilter
    ? payments.filter(p => p.final_status === activeFilter)
    : payments

  // Count per filter
  const counts = {}
  payments.forEach(p => {
    const s = p.final_status || 'pending'
    counts[s] = (counts[s] || 0) + 1
  })

  const backendOk = health !== null

  return (
    <div className="app">
      {/* ── Header ─────────────────────────────────────────────── */}
      <header className="header">
        <div className="header-inner">
          <div className="header-brand">
            <div className="header-logo">
              <div className="logo-icon">R</div>
              <div>
                <div className="header-title">RecoverIQ</div>
                <div className="header-subtitle">Policy-gated AI revenue recovery</div>
              </div>
            </div>
            <div className="header-divider" />
            <span className="badge-demo">Demo Mode</span>
            <span className="badge-mode">{mode}</span>
          </div>
          <div className="header-actions">
            {!backendOk && (
              <span style={{ fontSize: 12, color: '#dc2626' }}>⚠ Backend offline</span>
            )}
            <button
              id="run-recovery-batch-btn"
              className={`btn btn-primary ${loading ? 'btn-loading' : ''}`}
              onClick={handleRunBatch}
              disabled={loading || !backendOk}
            >
              {loading ? <span className="spinner" /> : '▶'}
              {loading ? 'Running…' : 'Run Recovery Batch'}
            </button>
          </div>
        </div>
      </header>

      <div className="main-content">

        {/* ── Error banner ────────────────────────────────────── */}
        {error && (
          <div className="error-banner" style={{ marginTop: 16 }}>
            <span className="error-icon">⚠</span>
            <div>
              <strong>Error:</strong> {error}
              <div style={{ marginTop: 4, fontSize: 12, opacity: 0.8 }}>
                Make sure the backend is running: <code>uvicorn app.main:app --reload</code> in the <code>backend/</code> directory.
              </div>
            </div>
          </div>
        )}

        {/* ── Metrics Strip ───────────────────────────────────── */}
        <div className="metrics-section">
          <div className="metrics-grid">
            <MetricCard
              label="At Risk"
              value={metrics ? fmtFull(metrics.total_at_risk) : '—'}
              sub={`${metrics?.total_payments || 0} payments`}
            />
            <MetricCard
              label="AI Recovered"
              value={metrics ? fmtFull(metrics.ai_recovered_amount) : '—'}
              sub={`${metrics?.ai_recovered_count || 0} payments`}
              color="green"
            />
            <MetricCard
              label="Blind Retry"
              value={metrics ? fmtFull(metrics.blind_retry_recovered_amount) : '—'}
              sub={`${metrics?.blind_retry_recovered_count || 0} payments (no AI)`}
            />
            <MetricCard
              label="AI Uplift"
              value={metrics
                ? (metrics.recovery_rate - metrics.blind_retry_rate).toFixed(1) + 'pp'
                : '—'}
              sub={metrics
                ? `${metrics.recovery_rate}% vs ${metrics.blind_retry_rate}% baseline`
                : 'vs blind retry'}
              color="blue"
              extra={metrics && (
                <span className="uplift-badge">
                  ↑ {fmtFull(metrics.ai_uplift_amount)} extra
                </span>
              )}
            />
            <MetricCard
              label="Recovery Rate"
              value={metrics ? metrics.recovery_rate + '%' : '—'}
              sub="AI-guided recovery"
              color={metrics && metrics.recovery_rate >= 25 ? 'green' : ''}
            />
            <MetricCard
              label="Blocked"
              value={metrics?.blocked_actions ?? '—'}
              sub="by policy engine"
              color="red"
            />
            <MetricCard
              label="Escalated / Other"
              value={metrics
                ? (metrics.escalated_count + metrics.needs_customer_action_count + metrics.unresolved_count)
                : '—'}
              sub={metrics
                ? `${metrics.escalated_count} escalated · ${metrics.needs_customer_action_count} customer action`
                : 'escalated + needs action'}
              color="amber"
            />
          </div>
        </div>

        {/* ── Info note (before first batch run) ─────────────── */}
        {!batchRan && !loading && (
          <div className="info-note" style={{ marginTop: 16 }}>
            <span>ℹ</span>
            <span>
              Click <strong>Run Recovery Batch</strong> to process all 50 synthetic payments through the
              AI diagnosis → policy engine → recovery simulator pipeline.
              The system runs in <strong>DEMO_MODE</strong> — no external AI calls, no real charges.
            </span>
          </div>
        )}

        {/* ── Payments Table ──────────────────────────────────── */}
        <div className="section-header" style={{ marginTop: 20 }}>
          <div>
            <div className="section-title">Payment Records</div>
            <div className="section-sub">
              {batchRan
                ? `${payments.length} payments processed · simulated/test-mode recovery`
                : 'Awaiting batch run'}
            </div>
          </div>
          <div className="filter-bar">
            {FILTERS.map(f => {
              const cnt = f.value ? (counts[f.value] || 0) : payments.length
              return (
                <button
                  key={f.value ?? 'all'}
                  id={`filter-${f.value ?? 'all'}`}
                  className={`filter-btn ${activeFilter === f.value ? 'active' : ''}`}
                  onClick={() => setActiveFilter(f.value)}
                >
                  {f.label}
                  {batchRan && cnt > 0 && (
                    <span className="filter-count">{cnt}</span>
                  )}
                </button>
              )
            })}
          </div>
        </div>

        <div className="table-container">
          {loading ? (
            <div className="empty-state">
              <div className="empty-state-icon">⏳</div>
              <div className="empty-state-title">Running recovery pipeline…</div>
              <div className="empty-state-sub">
                Diagnosing all 50 payments, evaluating policy rules, simulating recovery actions.
              </div>
            </div>
          ) : filteredPayments.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📋</div>
              <div className="empty-state-title">
                {batchRan ? 'No payments match this filter' : 'No batch run yet'}
              </div>
              <div className="empty-state-sub">
                {batchRan
                  ? 'Try a different filter or view all payments.'
                  : 'Click "Run Recovery Batch" to process the 50 synthetic payment records.'}
              </div>
            </div>
          ) : (
            <>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Payment · Customer</th>
                      <th>Amount</th>
                      <th>Failure Type</th>
                      <th>AI Diagnosis</th>
                      <th>Policy Decision</th>
                      <th>Action Taken</th>
                      <th>Final Status</th>
                      <th>Recovered</th>
                      <th>Audit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPayments.map(p => (
                      <PaymentRow
                        key={p.payment_id}
                        payment={p}
                        batchRan={batchRan}
                        expanded={expandedRow === p.payment_id}
                        onToggle={toggleRow}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="table-footer">
                <span className="table-count">
                  {filteredPayments.length} of {payments.length} payments
                </span>
                <span>
                  Simulated/test-mode data only · No real money recovered · No real charges made
                </span>
              </div>
            </>
          )}
        </div>

        {/* ── Audio Card ──────────────────────────────────────── */}
        <AudioCard />

        {/* ── Footer note ─────────────────────────────────────── */}
        <div style={{ marginTop: 24, padding: '12px 16px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 11, color: '#64748b', lineHeight: 1.7 }}>
          <strong>RecoverIQ — Demo Mode</strong> · Built for the Razorpay AI Builder Internship 2026 Buildathon ·
          Track: AI Revenue Recovery · This project uses synthetic and test-mode data only.
          No real money is charged. No real phone calls are made.
          The LLM proposes; the policy engine disposes.
        </div>
      </div>
    </div>
  )
}
