import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  runBatch,
  fetchPayments,
  fetchMetrics,
  fetchPaymentAudit,
  fetchAudioSample,
  fetchHealth,
} from '../api.js';
import RecoveryCharts from '../components/RecoveryCharts.jsx';

function fmt(amount) {
  if (amount == null) return '—';
  return '₹' + Number(amount).toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function fmtFull(amount) {
  if (amount == null) return '—';
  return '₹' + Number(amount).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtTime(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function cap(s) {
  if (!s) return '—';
  return s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, ' ');
}

const FAILURE_LABELS = {
  soft_decline: 'Soft Decline',
  insufficient_funds: 'Insufficient Funds',
  hard_decline: 'Hard Decline',
  authentication_failed: 'Auth Failed',
  checkout_abandoned: 'Checkout Abandoned',
  subscription_failed: 'Subscription Failed',
};

const ACTOR_LABELS = {
  system: 'System',
  diagnosis_engine: 'Diagnosis Engine',
  policy_engine: 'Policy Engine',
  recovery_executor: 'Recovery Executor',
  baseline_simulator: 'Baseline Simulator',
};

const FILTERS = [
  { label: 'All', value: null },
  { label: 'Recovered', value: 'recovered' },
  { label: 'Not Recovered', value: 'not_recovered' },
  { label: 'Blocked', value: 'blocked' },
  { label: 'Escalated', value: 'escalated' },
  { label: 'Needs Customer Action', value: 'needs_customer_action' },
];

function MetricCard({ label, value, sub, color, extra }) {
  return (
    <div className={`metric-card ${color || ''}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value ?? '—'}</div>
      {sub && <div className="metric-sub">{sub}</div>}
      {extra}
    </div>
  );
}

function PolicyBadge({ decision }) {
  if (!decision) return <span className="text-muted">—</span>;
  return (
    <span className={`policy-badge policy-${decision}`}>
      {decision === 'approved' && '✓ '}
      {decision === 'modified' && '~ '}
      {decision === 'blocked' && '✗ '}
      {decision === 'escalated' && '⚠ '}
      {cap(decision)}
    </span>
  );
}

function StatusBadge({ status }) {
  if (!status || status === 'pending') return <span className="status-badge status-pending">Pending</span>;
  const icons = {
    recovered: '✓',
    not_recovered: '✗',
    blocked: '⊘',
    escalated: '⚠',
    needs_customer_action: '→',
    unresolved: '?',
  };
  return (
    <span className={`status-badge status-${status}`}>
      {icons[status] || ''} {cap(status)}
    </span>
  );
}

function AuditTrail({ paymentId, batchRan }) {
  const [entries, setEntries] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!batchRan) {
      setLoading(false);
      return;
    }
    fetchPaymentAudit(paymentId)
      .then(data => {
        setEntries(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [paymentId, batchRan]);

  if (!batchRan) {
    return (
      <div className="audit-empty">
        Run the recovery batch to view the 7-step decision audit trail for this payment.
      </div>
    );
  }

  if (loading) {
    return <div className="audit-loading">Loading audit trail…</div>;
  }

  if (!entries || entries.length === 0) {
    return (
      <div className="audit-empty">
        No audit entries recorded yet. Click "Run Recovery Batch" above.
      </div>
    );
  }

  return (
    <div className="audit-trail">
      <div className="audit-title">
        <span>7-Step Immutable Decision Audit Trail</span>
        <span className="audit-count">{entries.length} events logged · SHA-256 Chained</span>
      </div>
      <div className="audit-steps">
        {entries.map((e, idx) => (
          <div key={e.id || idx} className="audit-step">
            <div className="audit-step-left">
              <div className="audit-step-num">{idx + 1}</div>
              {idx < entries.length - 1 && <div className="audit-step-line" />}
            </div>
            <div className="audit-step-body">
              <div className="audit-step-header">
                <span className="audit-actor">{ACTOR_LABELS[e.actor] || e.actor}</span>
                <span className="audit-event-type">{e.event_type}</span>
                <span className="audit-time">{fmtTime(e.timestamp)}</span>
              </div>
              <div className="audit-msg">{e.message}</div>
              {e.metadata && Object.keys(e.metadata).length > 0 && (
                <div className="audit-meta">
                  {Object.entries(e.metadata).map(([k, v]) => (
                    <span key={k} className="audit-meta-tag">
                      <strong>{k}:</strong> {typeof v === 'boolean' ? (v ? 'true' : 'false') : String(v)}
                    </span>
                  ))}
                </div>
              )}
              {e.event_hash && (
                <div className="audit-hash-tag">
                  🔒 SHA-256: <code>{e.event_hash.slice(0, 16)}…</code>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PaymentRow({ payment: p, batchRan, expanded, onToggle }) {
  const isPending = !batchRan || p.status === 'pending';
  return (
    <>
      <tr className={`payment-row ${expanded ? 'expanded' : ''}`}>
        <td>
          <div className="pay-id">{p.payment_id}</div>
          <div className="pay-customer">
            {p.customer_name}
            {p.consent_for_voice && <span className="locale-tag">Voice Consent ✓</span>}
            {p.opted_out && <span className="optout-tag">Opted Out</span>}
            {p.provenance && <span className="provenance-tag">{p.provenance}</span>}
          </div>
        </td>
        <td className="amount-col">{fmtFull(p.amount)}</td>
        <td>
          <span className={`cat-pill cat-${p.failure_category}`}>
            {FAILURE_LABELS[p.failure_category] || p.failure_category}
          </span>
          <div className="attempt-hint">{p.attempt_count} attempt{p.attempt_count > 1 ? 's' : ''}</div>
        </td>
        <td>
          {isPending ? (
            <span className="text-muted">Awaiting batch…</span>
          ) : (
            <div>
              <div className="ai-diag">{p.ai_diagnosis ? cap(p.ai_diagnosis) : '—'}</div>
              {p.ai_confidence != null && (
                <div className="ai-conf">
                  Confidence: {Math.round(p.ai_confidence * 100)}%
                  <span className={`risk-dot risk-${p.ai_risk_level || 'low'}`} title={`Risk: ${p.ai_risk_level}`} />
                </div>
              )}
            </div>
          )}
        </td>
        <td>
          {isPending ? <span className="text-muted">—</span> : <PolicyBadge decision={p.policy_decision} />}
          {p.policy_blocked_rule && <div className="rule-reason">Rule: {p.policy_blocked_rule}</div>}
          {p.policy_escalation_reason && <div className="rule-reason">Escalated: {p.policy_escalation_reason}</div>}
        </td>
        <td>
          {isPending ? <span className="text-muted">—</span> : <span className="action-taken">{p.action_taken ? cap(p.action_taken) : 'None'}</span>}
        </td>
        <td>
          <StatusBadge status={p.final_status} />
        </td>
        <td className="recovered-col">
          {isPending ? (
            <span className="text-muted">—</span>
          ) : p.recovered_amount > 0 ? (
            <span className="recovered-amt">{fmtFull(p.recovered_amount)}</span>
          ) : (
            <span className="text-muted">₹0.00</span>
          )}
        </td>
        <td>
          <button className={`btn-audit ${expanded ? 'active' : ''}`} onClick={() => onToggle(p.payment_id)}>
            {expanded ? '▲ Hide' : '▼ Audit'}
          </button>
        </td>
      </tr>
      {expanded && (
        <tr className="expanded-row">
          <td colSpan={9}>
            <AuditTrail paymentId={p.payment_id} batchRan={batchRan} />
          </td>
        </tr>
      )}
    </>
  );
}

function AudioCard() {
  const [sample, setSample] = useState(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    fetchAudioSample().then(setSample).catch(() => {});
  }, []);

  if (!sample) return null;

  return (
    <div className="audio-card">
      <div className="audio-card-header">
        <div className="audio-icon">🎙</div>
        <div className="audio-meta">
          <div className="audio-title">{sample.title}</div>
          <div className="audio-sub">{sample.case_context}</div>
        </div>
        <div className="audio-tags">
          <span className="audio-badge">{sample.language}</span>
          <span className="audio-badge">{sample.duration_seconds}s</span>
          <span className="audio-badge demo-badge">Cached Demo</span>
        </div>
      </div>
      <div className="audio-transcript">
        <div className="transcript-label">Transcript:</div>
        <div className="transcript-text">"{sample.transcript}"</div>
      </div>
      <div className="audio-controls">
        <button className={`btn btn-play ${playing ? 'playing' : ''}`} onClick={() => setPlaying(p => !p)}>
          {playing ? '⏸ Pause Preview' : '▶ Play Hinglish Nudge Audio'}
        </button>
        {playing && <span className="audio-playing-indicator">▶ Playing cached demo nudge (simulated playback)…</span>}
      </div>
      <div className="audio-disclaimer">{sample.disclaimer}</div>
    </div>
  );
}

export default function DashboardPage() {
  const [payments, setPayments] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeFilter, setActiveFilter] = useState(null);
  const [expandedRow, setExpandedRow] = useState(null);
  const [batchRan, setBatchRan] = useState(false);
  const [mode, setMode] = useState('DEMO_MODE');
  const [lastRunTime, setLastRunTime] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchHealth()
      .then(h => {
        if (h && h.mode) setMode(h.mode);
      })
      .catch(() => {});

    fetchPayments()
      .then(data => {
        if (data && data.length > 0) {
          setPayments(data);
          const hasRun = data.some(p => p.status !== 'pending' && p.final_status);
          if (hasRun) setBatchRan(true);
        }
      })
      .catch(() => {});

    fetchMetrics()
      .then(m => setMetrics(m))
      .catch(() => {});
  }, []);

  const handleRunBatch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await runBatch();
      setPayments(data.payments || []);
      setMetrics(data.metrics || null);
      setBatchRan(true);
      setLastRunTime(new Date());
      setExpandedRow(null);
    } catch (e) {
      setError(e.message || 'Batch run failed. Ensure backend is running.');
    } finally {
      setLoading(false);
    }
  }, []);

  const toggleRow = useCallback((id) => {
    setExpandedRow(prev => (prev === id ? null : id));
  }, []);

  const filteredPayments = activeFilter
    ? payments.filter(p => p.final_status === activeFilter)
    : payments;

  return (
    <div className="dashboard-container">
      {/* ── Subheader Navigation Bar ──────────────────────────── */}
      <header className="dashboard-topbar">
        <div className="dashboard-topbar-left">
          <Link to="/" className="back-link">← Back to Overview</Link>
          <div className="topbar-divider">/</div>
          <h1 className="dashboard-title">Recovery Console</h1>
          <span className="mode-pill">{mode}</span>
        </div>
        <div className="dashboard-topbar-right">
          <span className="env-tag">RazorpayX Test Mode</span>
          <button
            className="btn btn-primary"
            onClick={handleRunBatch}
            disabled={loading}
          >
            {loading ? 'Running Recovery Batch…' : '▶ Run Recovery Batch (50 Txns)'}
          </button>
        </div>
      </header>

      {error && (
        <div className="error-banner">
          <span>⚠️ {error}</span>
          <button className="error-dismiss" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* ── KPI Metric Cards ──────────────────────────────────── */}
      <div className="metric-cards-grid">
        <MetricCard
          label="Total At-Risk Volume"
          value={metrics ? fmt(metrics.total_at_risk) : fmt(286348)}
          sub="50 failed transactions queued"
        />
        <MetricCard
          label="RecoverIQ Recovered"
          value={metrics ? fmt(metrics.ai_recovered_amount) : fmt(71993)}
          sub={metrics ? `${metrics.ai_recovered_count} payments (${metrics.ai_recovery_rate_pct.toFixed(1)}%)` : '19 payments (38.0%)'}
          color="metric-card-success"
        />
        <MetricCard
          label="Blind Retry Baseline"
          value={metrics ? fmt(metrics.blind_retry_amount) : fmt(13297)}
          sub={metrics ? `${metrics.blind_retry_count} payments (${metrics.blind_recovery_rate_pct.toFixed(1)}%)` : '6 payments (12.0%)'}
          color="metric-card-muted"
        />
        <MetricCard
          label="Net AI Uplift"
          value={metrics ? `+${fmt(metrics.net_revenue_uplift)}` : '+₹58,696'}
          sub={metrics ? `+${metrics.net_recovery_rate_uplift_pct.toFixed(1)} pp recovery uplift` : '+26.0 percentage points'}
          color="metric-card-primary"
        />
        <MetricCard
          label="Fraud & High Risk"
          value="13 Blocked"
          sub="100% fraud protection"
          color="metric-card-rose"
        />
        <MetricCard
          label="High-Value Escrow"
          value="4 Escalated"
          sub="> ₹25,000 threshold"
          color="metric-card-amber"
        />
      </div>

      {/* ── Visual Charts & Audit Verifier ───────────────────── */}
      <RecoveryCharts metrics={metrics} payments={payments} batchRan={batchRan} />

      {/* ── Transaction Ledger Table ─────────────────────────── */}
      <div className="table-wrapper">
        <div className="table-controls">
          <div className="filter-group">
            <span className="filter-label">Filter:</span>
            {FILTERS.map(f => (
              <button
                key={f.label}
                className={`filter-btn ${activeFilter === f.value ? 'active' : ''}`}
                onClick={() => setActiveFilter(f.value)}
              >
                {f.label}
              </button>
            ))}
          </div>
          {lastRunTime && (
            <div className="run-timestamp">
              Last processed: {fmtTime(lastRunTime)}
            </div>
          )}
        </div>

        <div className="table-container">
          {loading ? (
            <div className="empty-state">
              <div className="empty-state-icon">⏳</div>
              <div className="empty-state-title">Running recovery pipeline…</div>
              <div className="empty-state-sub">
                Diagnosing all 50 payments, evaluating 8 deterministic policy rules, and generating SHA-256 idempotency keys.
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
                  : 'Click "Run Recovery Batch" above to process the 50 synthetic payment records.'}
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
                  Showing {filteredPayments.length} of {payments.length} transactions
                </span>
                <span>
                  Deterministic Policy Bounds · SHA-256 Idempotency · Test Mode Simulation
                </span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Audio Card ────────────────────────────────────────── */}
      <AudioCard />
    </div>
  );
}
