"""
Deterministic Policy Engine Boundary & Precedence Test Suite.

Verifies:
1. Strict boundary conditions for all 8 policy rules:
   - Rule 1: already_recovered
   - Rule 2: customer_opted_out
   - Rule 3: hard_decline_no_retry
   - Rule 4: max_retries_reached (attempt_count >= 3)
   - Rule 5: high_value_threshold (amount > ₹25,000)
   - Rule 6: low_confidence (confidence < 0.60)
   - Rule 7: voice_consent_missing (suppress voice)
   - Rule 8: standard approval
2. Multi-rule precedence ordering (First match wins).
3. Exact boundary edge values (₹25,000.00 vs ₹25,000.01; 0.60 vs 0.599; attempt 2 vs 3).
"""
import pytest
from app.policy import evaluate_policy, _make_idempotency_key
from app.schemas import DiagnosisOutput


def _diag(cat="soft_decline", conf=0.85, action="retry_later", risk="low"):
    return DiagnosisOutput(
        diagnosis=cat,
        confidence=conf,
        reasoning_summary="Boundary test diagnosis",
        recommended_action=action,
        customer_message_needed=False,
        risk_level=risk,
    )


# ── Rule 1 Boundary: Already Recovered ─────────────────────────────────────────
def test_policy_rule1_already_recovered():
    pol = evaluate_policy("p1", "soft_decline", 1000.0, 1, False, False, "recovered", _diag(), "r1")
    assert pol.decision == "blocked"
    assert pol.blocked_rule == "already_recovered"


def test_policy_rule1_not_recovered_proceeds():
    pol = evaluate_policy("p1", "soft_decline", 1000.0, 1, False, False, "not_recovered", _diag(), "r1")
    assert pol.decision == "approved"


# ── Rule 2 Boundary: Opted-Out Customer ───────────────────────────────────────
def test_policy_rule2_opted_out_blocks():
    pol = evaluate_policy("p2", "soft_decline", 1000.0, 1, True, False, "pending", _diag(), "r1")
    assert pol.decision == "blocked"
    assert pol.blocked_rule == "customer_opted_out"


# ── Rule 3 Boundary: Hard Decline ─────────────────────────────────────────────
def test_policy_rule3_hard_decline_blocks():
    pol = evaluate_policy("p3", "hard_decline", 1000.0, 1, False, False, "pending", _diag(cat="hard_decline", action="stop_no_retry"), "r1")
    assert pol.decision == "blocked"
    assert pol.blocked_rule == "hard_decline_no_retry"


# ── Rule 4 Boundary: Max Retries (Attempt >= 3) ───────────────────────────────
def test_policy_rule4_attempt_exactly_2_proceeds():
    pol = evaluate_policy("p4", "soft_decline", 1000.0, 2, False, False, "pending", _diag(), "r1")
    assert pol.decision == "approved"


def test_policy_rule4_attempt_exactly_3_blocks():
    pol = evaluate_policy("p4", "soft_decline", 1000.0, 3, False, False, "pending", _diag(), "r1")
    assert pol.decision == "blocked"
    assert pol.blocked_rule == "max_retries_reached"


def test_policy_rule4_attempt_4_blocks():
    pol = evaluate_policy("p4", "soft_decline", 1000.0, 4, False, False, "pending", _diag(), "r1")
    assert pol.decision == "blocked"
    assert pol.blocked_rule == "max_retries_reached"


# ── Rule 5 Boundary: High Value Threshold (> ₹25,000) ─────────────────────────
def test_policy_rule5_amount_exactly_25000_does_not_escalate():
    """At exactly ₹25,000.00, rule 5 does not escalate (> 25000 strictly)."""
    pol = evaluate_policy("p5", "soft_decline", 25000.0, 1, False, False, "pending", _diag(), "r1")
    assert pol.decision == "approved"
    assert pol.selected_action == "retry_later"


def test_policy_rule5_amount_25000_01_escalates():
    """At ₹25,000.01, rule 5 triggers high_value_threshold escalation."""
    pol = evaluate_policy("p5", "soft_decline", 25000.01, 1, False, False, "pending", _diag(), "r1")
    assert pol.decision == "escalated"
    assert pol.escalation_reason == "high_value_threshold"


def test_policy_rule5_amount_24999_99_proceeds():
    pol = evaluate_policy("p5", "soft_decline", 24999.99, 1, False, False, "pending", _diag(), "r1")
    assert pol.decision == "approved"


# ── Rule 6 Boundary: Low Confidence (< 0.60) ──────────────────────────────────
def test_policy_rule6_confidence_exactly_0_60_proceeds():
    """At confidence exactly 0.60, rule 6 does not escalate (< 0.60 strictly)."""
    pol = evaluate_policy("p6", "soft_decline", 1000.0, 1, False, False, "pending", _diag(conf=0.60), "r1")
    assert pol.decision == "approved"


def test_policy_rule6_confidence_0_599_escalates():
    """At confidence 0.599, rule 6 triggers low_confidence escalation."""
    pol = evaluate_policy("p6", "soft_decline", 1000.0, 1, False, False, "pending", _diag(conf=0.599), "r1")
    assert pol.decision == "escalated"
    assert pol.escalation_reason == "low_confidence"


# ── Rule 7 Boundary: Voice Consent Channel Suppression ────────────────────────
def test_policy_rule7_voice_action_without_consent_is_modified():
    diag = _diag(action="retry_plus_reminder")
    pol = evaluate_policy("p7", "soft_decline", 1000.0, 1, False, False, "pending", diag, "r1")
    assert pol.decision == "modified"
    assert pol.selected_action == "retry_later"
    assert "Voice channel suppressed" in pol.reason


def test_policy_rule7_voice_action_with_consent_is_approved():
    diag = _diag(action="retry_plus_reminder")
    pol = evaluate_policy("p7", "soft_decline", 1000.0, 1, False, True, "pending", diag, "r1")
    assert pol.decision == "approved"
    assert pol.selected_action == "retry_plus_reminder"


# ── Precedence Ordering (First Match Wins) ────────────────────────────────────
def test_precedence_rule1_over_rule2():
    """Already recovered beats opted out."""
    pol = evaluate_policy("pp1", "soft_decline", 1000.0, 1, True, False, "recovered", _diag(), "r1")
    assert pol.decision == "blocked"
    assert pol.blocked_rule == "already_recovered"


def test_precedence_rule2_over_rule3():
    """Opted out beats hard decline."""
    pol = evaluate_policy("pp2", "hard_decline", 1000.0, 1, True, False, "pending", _diag(cat="hard_decline"), "r1")
    assert pol.decision == "blocked"
    assert pol.blocked_rule == "customer_opted_out"


def test_precedence_rule3_over_rule5():
    """Hard decline blocks before high value can escalate."""
    pol = evaluate_policy("pp3", "hard_decline", 50000.0, 1, False, False, "pending", _diag(cat="hard_decline"), "r1")
    assert pol.decision == "blocked"
    assert pol.blocked_rule == "hard_decline_no_retry"


def test_precedence_rule5_over_rule6():
    """High value threshold escalates before low confidence."""
    pol = evaluate_policy("pp4", "soft_decline", 30000.0, 1, False, False, "pending", _diag(conf=0.40), "r1")
    assert pol.decision == "escalated"
    assert pol.escalation_reason == "high_value_threshold"
