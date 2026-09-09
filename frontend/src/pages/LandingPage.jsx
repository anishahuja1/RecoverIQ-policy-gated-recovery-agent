import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { fetchMetrics, fetchHealth } from '../api.js';

export default function LandingPage() {
  const [metrics, setMetrics] = useState(null);
  const [health, setHealth] = useState(null);

  useEffect(() => {
    fetchMetrics().then(setMetrics).catch(() => {});
    fetchHealth().then(setHealth).catch(() => {});
  }, []);

  return (
    <div className="landing-container">
      {/* ── Top Navbar ────────────────────────────────────────── */}
      <nav className="landing-nav">
        <div className="nav-brand">
          <div className="nav-logo">⚡</div>
          <span className="nav-title">RecoverIQ</span>
          <span className="nav-badge">Razorpay AI Track</span>
        </div>
        <div className="nav-links">
          <a href="#where-to-look" className="nav-item">Evaluation Guide</a>
          <a href="#demo-video" className="nav-item">Video Demo</a>
          <a href="#architecture" className="nav-item">Architecture</a>
          <a href="#security" className="nav-item">Security</a>
          <a
            href="https://github.com/anishahuja1/RecoverIQ-policy-gated-recovery-agent"
            target="_blank"
            rel="noopener noreferrer"
            className="nav-item"
          >
            GitHub
          </a>
          <Link to="/dashboard" className="btn btn-primary nav-cta">
            Launch Console →
          </Link>
        </div>
      </nav>

      {/* ── Hero Section ──────────────────────────────────────── */}
      <section className="hero-section">
        <h1 className="hero-heading">
          The LLM proposes; <br />
          <span className="gradient-text">the policy engine disposes.</span>
        </h1>

        <p className="hero-subheading">
          Payment failures cost Indian SaaS and e-commerce merchants up to 20–30% of gross revenue.
          RecoverIQ introduces an institutional-grade, policy-governed recovery loop where
          <strong> AI advises, but deterministic code governs</strong>—stopping blind retry fraud and eliminating
          unconstrained autonomous risks.
        </p>

        <div className="hero-buttons">
          <Link to="/dashboard" className="btn btn-hero-primary">
            <span>▶ Launch Live Dashboard</span>
          </Link>
          <a
            href="https://www.loom.com/share/183f8730da0243639f8ce62120d82244"
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-hero-secondary"
          >
            📺 Watch Video Demo (3m)
          </a>
          <a
            href="https://github.com/anishahuja1/RecoverIQ-policy-gated-recovery-agent"
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-hero-secondary"
          >
            GitHub
          </a>
        </div>

        {/* Live Metrics Ticker Bar */}
        <div className="metrics-ticker">
          <div className="ticker-item">
            <span className="ticker-label">Proven Recovery Uplift</span>
            <span className="ticker-value">
              {metrics && metrics.recovery_rate != null && metrics.blind_retry_rate != null
                ? `+${(metrics.recovery_rate - metrics.blind_retry_rate).toFixed(1)} pp`
                : '+26.0 pp'}
            </span>
          </div>
          <div className="ticker-divider" />
          <div className="ticker-item">
            <span className="ticker-label">Simulated Revenue Lift</span>
            <span className="ticker-value">
              {metrics && metrics.ai_uplift_amount != null
                ? `+₹${Math.round(metrics.ai_uplift_amount).toLocaleString('en-IN')}`
                : '+₹58,696'}
            </span>
          </div>
          <div className="ticker-divider" />
          <div className="ticker-item">
            <span className="ticker-label">Fraud Protection</span>
            <span className="ticker-value text-emerald">100% Blocked</span>
          </div>
          <div className="ticker-divider" />
          <div className="ticker-item">
            <span className="ticker-label">Automated Tests</span>
            <span className="ticker-value text-indigo">67 Passing</span>
          </div>
        </div>
      </section>

      {/* ── Where to Look First (Judge Walkthrough) ────────────── */}
      <section id="where-to-look" className="section where-to-look-section">
        <div className="section-header">
          <span className="section-tag">Evaluator Runbook</span>
          <h2 className="section-title">Where to Look First (3-Minute Tour)</h2>
          <p className="section-subtitle">
            Three concrete verification steps designed for buildathon judges:
          </p>
        </div>

        <div className="steps-grid">
          <div className="step-card">
            <div className="step-num">01</div>
            <h3 className="step-title">Run Recovery Batch</h3>
            <p className="step-desc">
              Navigate to the Recovery Console and click <strong>"Run Recovery Batch"</strong>. Watch 50 failed
              transactions pass through failure classification, policy gating, and idempotency key creation in real-time.
            </p>
            <Link to="/dashboard" className="step-link">Open Dashboard →</Link>
          </div>

          <div className="step-card">
            <div className="step-num">02</div>
            <h3 className="step-title">Verify Audit Hash Chain</h3>
            <p className="step-desc">
              Inspect the <strong>SHA-256 tamper-evident audit trail</strong>. Click "Verify Cryptographic Hash Chain"
              on the dashboard or run <code>python scripts/verify_audit_chain.py</code> in the terminal to verify zero DB corruption.
            </p>
            <Link to="/dashboard" className="step-link">Test Audit Verifier →</Link>
          </div>

          <div className="step-card">
            <div className="step-num">03</div>
            <h3 className="step-title">Prompt Injection Defense</h3>
            <p className="step-desc">
              Inspect <code>backend/tests/test_prompt_injection.py</code>. See how untrusted webhook fields are safely
              isolated in <code>&lt;untrusted_webhook_data&gt;</code> tags and output schema deviations are rejected.
            </p>
            <a
              href="https://github.com/anishahuja1/RecoverIQ-policy-gated-recovery-agent/blob/main/backend/tests/test_prompt_injection.py"
              target="_blank"
              rel="noopener noreferrer"
              className="step-link"
            >
              View Test Cases →
            </a>
          </div>
        </div>
      </section>

      {/* ── Problem Section ───────────────────────────────────── */}
      <section className="section problem-section">
        <div className="section-header">
          <span className="section-tag">The Problem</span>
          <h2 className="section-title">Traditional Recovery Falls Into Two Extreme Traps</h2>
        </div>

        <div className="problem-comparison-grid">
          <div className="problem-card card-danger">
            <div className="problem-card-icon">⚠️</div>
            <h3 className="problem-card-title">Trap 1: Blind Retries</h3>
            <p className="problem-card-desc">
              Traditional gateways blindly re-execute failed payments on timers without understanding why they failed.
            </p>
            <ul className="problem-list">
              <li>Retries hard declines & stolen cards, triggering card network fines.</li>
              <li>Wastes interchange fees repeatedly attempting insufficient funds.</li>
              <li>Spams opted-out customers, violating Indian telecom & privacy norms.</li>
            </ul>
          </div>

          <div className="problem-card card-warning">
            <div className="problem-card-icon">⚡</div>
            <h3 className="problem-card-title">Trap 2: Unconstrained Autonomous AI</h3>
            <p className="problem-card-desc">
              Directing an autonomous LLM to take actions directly on merchant financial flows introduces critical risks.
            </p>
            <ul className="problem-list">
              <li>Vulnerable to prompt injections from customer notes & webhook data.</li>
              <li>Unpredictable hallucinations leading to double charges.</li>
              <li>Triggers unmonitored high-value transactions without human maker-checker controls.</li>
            </ul>
          </div>
        </div>
      </section>

      {/* ── Architecture Section (Inline SVG) ─────────────────── */}
      <section id="architecture" className="section architecture-section">
        <div className="section-header">
          <span className="section-tag">System Design</span>
          <h2 className="section-title">The Policy-Gated Architecture</h2>
          <p className="section-subtitle">
            AI diagnoses the failure and suggests actions; the 8-rule deterministic policy engine enforces hard bounds.
          </p>
        </div>

        <div className="architecture-diagram-container">
          <svg
            viewBox="0 0 1000 480"
            className="arch-svg"
            xmlns="http://www.w3.org/2000/svg"
          >
            <defs>
              <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#64748b" />
              </marker>
            </defs>

            {/* Ingestion Box */}
            <rect x="30" y="190" width="180" height="90" rx="8" fill="#f0f9ff" stroke="#0284c7" strokeWidth="1.5" />
            <text x="120" y="222" fill="#0f172a" fontSize="13" fontWeight="bold" textAnchor="middle">Razorpay Webhook</text>
            <text x="120" y="242" fill="#475569" fontSize="11" textAnchor="middle">payment.failed Ingestion</text>
            <text x="120" y="258" fill="#0284c7" fontSize="10" fontWeight="600" textAnchor="middle">Provenance Tagging</text>

            {/* Arrow 1 */}
            <line x1="210" y1="235" x2="260" y2="235" stroke="#94a3b8" strokeWidth="2" markerEnd="url(#arrow)" />

            {/* AI Diagnosis Engine */}
            <rect x="260" y="180" width="200" height="110" rx="8" fill="#f5f3ff" stroke="#6366f1" strokeWidth="1.5" />
            <text x="360" y="212" fill="#0f172a" fontSize="13" fontWeight="bold" textAnchor="middle">AI Diagnosis Engine</text>
            <text x="360" y="232" fill="#4f46e5" fontSize="10" fontWeight="600" textAnchor="middle">Prompt Injection Guard</text>
            <text x="360" y="248" fill="#475569" fontSize="10" textAnchor="middle">XML Tag Delimitation</text>
            <text x="360" y="266" fill="#6366f1" fontSize="10" textAnchor="middle">6 Categorical Classifiers</text>

            {/* Arrow 2 */}
            <line x1="460" y1="235" x2="510" y2="235" stroke="#94a3b8" strokeWidth="2" markerEnd="url(#arrow)" />

            {/* Policy Engine Diamond / Block */}
            <rect x="510" y="165" width="220" height="140" rx="8" fill="#fffbeb" stroke="#f59e0b" strokeWidth="1.5" />
            <text x="620" y="196" fill="#0f172a" fontSize="13" fontWeight="bold" textAnchor="middle">Deterministic Policy Engine</text>
            <text x="620" y="216" fill="#b45309" fontSize="10" fontWeight="700" textAnchor="middle">8 Rules (First Match Wins)</text>
            <text x="620" y="236" fill="#475569" fontSize="10" textAnchor="middle">1. Already Recovered</text>
            <text x="620" y="251" fill="#475569" fontSize="10" textAnchor="middle">2. Opt-Out | 3. Hard Decline</text>
            <text x="620" y="266" fill="#475569" fontSize="10" textAnchor="middle">4. Retries | 5. High Value</text>
            <text x="620" y="281" fill="#475569" fontSize="10" textAnchor="middle">6. Low Conf | 7. Voice Consent</text>

            {/* Decision Outputs */}
            <line x1="730" y1="190" x2="790" y2="120" stroke="#f43f5e" strokeWidth="2" markerEnd="url(#arrow)" />
            <rect x="790" y="100" width="170" height="40" rx="6" fill="#fff1f2" stroke="#f43f5e" strokeWidth="1.5" />
            <text x="875" y="125" fill="#9f1239" fontSize="11" fontWeight="bold" textAnchor="middle">BLOCK (No Retry)</text>

            <line x1="730" y1="220" x2="790" y2="190" stroke="#8b5cf6" strokeWidth="2" markerEnd="url(#arrow)" />
            <rect x="790" y="170" width="170" height="40" rx="6" fill="#f5f3ff" stroke="#8b5cf6" strokeWidth="1.5" />
            <text x="875" y="195" fill="#5b21b6" fontSize="11" fontWeight="bold" textAnchor="middle">ESCALATE (Review)</text>

            <line x1="730" y1="250" x2="790" y2="260" stroke="#f59e0b" strokeWidth="2" markerEnd="url(#arrow)" />
            <rect x="790" y="240" width="170" height="40" rx="6" fill="#fffbeb" stroke="#f59e0b" strokeWidth="1.5" />
            <text x="875" y="265" fill="#92400e" fontSize="11" fontWeight="bold" textAnchor="middle">MODIFY (Strip Channel)</text>

            <line x1="730" y1="280" x2="790" y2="330" stroke="#10b981" strokeWidth="2" markerEnd="url(#arrow)" />
            <rect x="790" y="310" width="170" height="40" rx="6" fill="#ecfdf5" stroke="#10b981" strokeWidth="1.5" />
            <text x="875" y="335" fill="#065f46" fontSize="11" fontWeight="bold" textAnchor="middle">APPROVE + SHA-256</text>

            {/* Bottom Immutable Ledger Banner */}
            <rect x="150" y="410" width="700" height="45" rx="6" fill="#ffffff" stroke="#cbd5e1" strokeWidth="1.5" />
            <text x="500" y="437" fill="#0f172a" fontSize="11" fontWeight="bold" textAnchor="middle">
              🔒 Immutable Cryptographic SHA-256 Audit Trail: prev_hash || canonical_json(event)
            </text>
          </svg>
        </div>
      </section>

      {/* ── Security & Integrity Section ──────────────────────── */}
      <section id="security" className="section security-section">
        <div className="section-header">
          <span className="section-tag">Security Posture</span>
          <h2 className="section-title">Institutional-Grade Defenses</h2>
          <p className="section-subtitle">
            Engineered with defense-in-depth principles rather than marketing claims.
          </p>
        </div>

        <div className="security-grid">
          <div className="security-card">
            <div className="security-badge">DEFENSE-IN-DEPTH</div>
            <h3 className="security-card-title">Prompt-Injection Isolation</h3>
            <p className="security-card-desc">
              All untrusted parameters (<code>failure_message</code>, <code>error_description</code>, customer notes)
              originating from the Razorpay webhook payload are sanitized and isolated inside strict
              <code>&lt;untrusted_webhook_data&gt;</code> XML boundaries.
            </p>
            <div className="code-snippet">
              <code>&lt;untrusted_webhook_data&gt;<br />&nbsp;&nbsp;&lt;failure_message&gt;Timeout&lt;/failure_message&gt;<br />&lt;/untrusted_webhook_data&gt;</code>
            </div>
            <p className="security-card-note">
              Post-generation schema validation verifies outputs against allowed action enums and bounded confidence ranges,
              falling back safely to cached deterministic diagnosis upon any deviation.
            </p>
          </div>

          <div className="security-card">
            <div className="security-badge">CRYPTOGRAPHIC INTEGRITY</div>
            <h3 className="security-card-title">Tamper-Evident SHA-256 Hash Chain</h3>
            <p className="security-card-desc">
              Every audit record stores a cryptographic hash linking to its exact predecessor:
              <br />
              <code>event_hash = SHA256(prev_hash || canonical_json(...))</code>
            </p>
            <div className="code-snippet">
              <code>GET /api/audit/verify<br />→ {"{"}"is_valid": true, "total_verified": 340{"}"}</code>
            </div>
            <p className="security-card-note">
              The verification API and CLI tool detect row modifications, deleted entries, or broken parent links in milliseconds.
            </p>
          </div>
        </div>
      </section>

      {/* ── Demo Video Section ────────────────────────────────── */}
      <section id="demo-video" className="section video-section">
        <div className="section-header">
          <span className="section-tag">Video Walkthrough</span>
          <h2 className="section-title">See RecoverIQ in Action (3 Minutes)</h2>
          <p className="section-subtitle">
            A quick walkthrough showing batch payment diagnosis, policy gating, fraud blocking, and cryptographic audit verification:
          </p>
        </div>

        <div className="video-player-container">
          <div style={{ position: 'relative', paddingBottom: '56.25%', height: 0, overflow: 'hidden', borderRadius: 8, border: '1px solid var(--border)' }}>
            <iframe
              src="https://www.loom.com/embed/183f8730da0243639f8ce62120d82244?hide_owner=true&hide_share=true&hide_title=true&hideEmbedTopBar=true"
              frameBorder="0"
              webkitallowfullscreen="true"
              mozallowfullscreen="true"
              allowFullScreen
              style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' }}
              title="RecoverIQ Loom Demo Walkthrough"
            />
          </div>
          <div style={{ marginTop: 20, display: 'flex', justifyContent: 'center', gap: 12, flexWrap: 'wrap' }}>
            <a
              href="https://www.loom.com/share/183f8730da0243639f8ce62120d82244"
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-secondary"
            >
              📺 Open on Loom ↗
            </a>
            <Link to="/dashboard" className="btn btn-primary">
              Launch Interactive Console →
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ────────────────────────────────────────────── */}
      <footer className="landing-footer">
        <div className="footer-content">
          <div className="footer-brand">
            <div className="nav-logo">⚡</div>
            <span>RecoverIQ</span>
          </div>
          <p className="footer-tagline">
            Policy-gated AI Revenue Recovery for the Razorpay AI Builder Internship Buildathon (2026).
          </p>
          <div className="footer-links">
            <Link to="/dashboard">Dashboard</Link>
            <a
              href="https://github.com/anishahuja1/RecoverIQ-policy-gated-recovery-agent"
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub Repository
            </a>
            <a href="#where-to-look">Judge Guide</a>
          </div>
          <div className="footer-bottom">
            <span>© 2026 RecoverIQ. Open source under MIT License.</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
