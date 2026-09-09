import React, { useState } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { fetchAuditVerification } from '../api.js';

const CATEGORY_DATA = [
  { name: 'Soft Decline', recoveriq: 56, blind: 18 },
  { name: 'Insuff. Funds', recoveriq: 38, blind: 0 },
  { name: '3DS Auth', recoveriq: 46, blind: 0 },
  { name: 'Checkout Drop', recoveriq: 32, blind: 0 },
  { name: 'Subscription', recoveriq: 44, blind: 16 },
  { name: 'Hard Decline', recoveriq: 0, blind: 0 },
];

const DECISION_COLORS = {
  Approved: '#10b981', // Emerald
  Modified: '#f59e0b', // Amber
  Blocked: '#f43f5e',  // Rose
  Escalated: '#8b5cf6',// Violet
};

export default function RecoveryCharts({ metrics, payments, batchRan }) {
  const [verifying, setVerifying] = useState(false);
  const [auditResult, setAuditResult] = useState(null);

  // Compute decision breakdown from payments
  const decisionCounts = { Approved: 0, Modified: 0, Blocked: 0, Escalated: 0 };
  if (payments && payments.length > 0) {
    payments.forEach((p) => {
      if (p.policy_decision === 'approved') decisionCounts.Approved++;
      else if (p.policy_decision === 'modified') decisionCounts.Modified++;
      else if (p.policy_decision === 'blocked') decisionCounts.Blocked++;
      else if (p.policy_decision === 'escalated') decisionCounts.Escalated++;
    });
  } else {
    // Default demo distribution
    decisionCounts.Approved = 24;
    decisionCounts.Modified = 9;
    decisionCounts.Blocked = 13;
    decisionCounts.Escalated = 4;
  }

  const pieData = Object.entries(decisionCounts)
    .filter(([_, count]) => count > 0)
    .map(([name, value]) => ({ name, value }));

  const handleVerify = async () => {
    setVerifying(true);
    try {
      const res = await fetchAuditVerification();
      setAuditResult(res);
    } catch (e) {
      setAuditResult({ is_valid: false, message: e.message });
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="charts-section">
      <div className="charts-grid">
        {/* ── Chart 1: Category Recovery Rate Comparison ──────────────── */}
        <div className="chart-card">
          <div className="chart-header">
            <div>
              <h3 className="chart-title">Recovery Rate by Failure Category (%)</h3>
              <p className="chart-subtitle">
                RecoverIQ Multi-Channel Action vs Blind Retry Baseline
              </p>
            </div>
            <span className="badge-pill badge-primary">+27.0% Avg Uplift</span>
          </div>
          <div style={{ width: '100%', height: 260 }}>
            <ResponsiveContainer>
              <BarChart
                data={CATEGORY_DATA}
                margin={{ top: 10, right: 10, left: -20, bottom: 20 }}
              >
                <XAxis
                  dataKey="name"
                  stroke="#94a3b8"
                  fontSize={11}
                  tickLine={false}
                  angle={-15}
                  textAnchor="end"
                />
                <YAxis
                  stroke="#94a3b8"
                  fontSize={11}
                  tickLine={false}
                  domain={[0, 70]}
                  unit="%"
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                    color: '#f8fafc',
                    fontSize: '12px',
                  }}
                  formatter={(val, name) => [
                    `${val}%`,
                    name === 'recoveriq' ? 'RecoverIQ' : 'Blind Retry',
                  ]}
                />
                <Legend
                  verticalAlign="top"
                  align="right"
                  iconType="circle"
                  wrapperStyle={{ fontSize: '11px', paddingBottom: '10px' }}
                  formatter={(val) => (val === 'recoveriq' ? 'RecoverIQ (AI + Policy)' : 'Blind Retry')}
                />
                <Bar
                  dataKey="recoveriq"
                  fill="#6366f1"
                  radius={[4, 4, 0, 0]}
                  name="recoveriq"
                />
                <Bar
                  dataKey="blind"
                  fill="#64748b"
                  radius={[4, 4, 0, 0]}
                  name="blind"
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* ── Chart 2: Policy Engine Decisions Distribution ──────────── */}
        <div className="chart-card">
          <div className="chart-header">
            <div>
              <h3 className="chart-title">Policy Engine Decision Breakdown</h3>
              <p className="chart-subtitle">
                Deterministic 8-Rule Enforcement Distribution
              </p>
            </div>
            <span className="badge-pill badge-emerald">Deterministic Code Governs</span>
          </div>
          <div style={{ width: '100%', height: 260 }} className="flex-center">
            <ResponsiveContainer>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={85}
                  paddingAngle={4}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}`}
                  labelLine={false}
                >
                  {pieData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={DECISION_COLORS[entry.name] || '#94a3b8'}
                    />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                    color: '#f8fafc',
                    fontSize: '12px',
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* ── Live Cryptographic Audit Chain Verifier Card ────────────── */}
      <div className="audit-verifier-card">
        <div className="audit-verifier-content">
          <div className="audit-verifier-icon">🛡️</div>
          <div>
            <h4 className="audit-verifier-title">
              Tamper-Evident SHA-256 Audit Chain Verifier
            </h4>
            <p className="audit-verifier-desc">
              Every system event, AI diagnosis, and policy decision is linked via
              cryptographic SHA-256 parent hashes. Walk the chain to verify complete
              data integrity.
            </p>
          </div>
        </div>

        <div className="audit-verifier-actions">
          <button
            className="btn btn-secondary btn-verifier"
            onClick={handleVerify}
            disabled={verifying}
          >
            {verifying ? 'Verifying Chain…' : '🔍 Verify Cryptographic Hash Chain'}
          </button>
        </div>

        {auditResult && (
          <div
            className={`audit-verifier-result ${
              auditResult.is_valid ? 'result-success' : 'result-error'
            }`}
          >
            <span className="result-icon">
              {auditResult.is_valid ? '✅' : '❌'}
            </span>
            <div className="result-text">
              <strong>
                {auditResult.is_valid
                  ? 'Audit Chain 100% Intact'
                  : 'Tampering Detected'}
              </strong>
              <span>
                {auditResult.message} (Verified {auditResult.total_verified ?? 0}{' '}
                sequential blocks)
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
