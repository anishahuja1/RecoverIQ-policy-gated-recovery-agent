"""
RecoverIQ Test Suite — Razorpay Builder Track Verification

Tests:
1. Deterministic Policy Engine (Rules 1 through 8 in priority order)
2. Idempotency Key Generation & Uniqueness
3. AI Diagnosis Engine & Fallback
4. Recovery Simulator & Blind Retry Baseline
5. Metrics Aggregation & AI Uplift Calculations
6. FastAPI Endpoints & Razorpay Webhook Ingestion
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.policy import evaluate_policy, _make_idempotency_key
from app.schemas import DiagnosisOutput, PolicyOutput
from app.diagnosis import run_demo_diagnosis
from app.recovery import simulate_recovery, simulate_blind_retry
from app.database import get_db, SessionLocal
from app.models import Payment, AuditLog


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _sample_diagnosis(cat="soft_decline", conf=0.86, action="retry_later", risk="low"):
    return DiagnosisOutput(
        diagnosis=cat,
        confidence=conf,
        reasoning_summary="Test reasoning",
        recommended_action=action,
        customer_message_needed=False,
        risk_level=risk,
    )


# ── 1. POLICY ENGINE TESTS (Rules 1-8 in Priority Order) ──────────────────────

def test_rule1_already_recovered_is_blocked():
    """Rule 1: Idempotency guard — already recovered payments must be blocked."""
    diag = _sample_diagnosis()
    pol = evaluate_policy(
        payment_id="pay_test_01",
        failure_category="soft_decline",
        amount=1000.0,
        attempt_count=1,
        opted_out=False,
        consent_for_voice=True,
        current_status="recovered",
        diagnosis=diag,
        run_id="run_01",
    )
    assert pol.decision == "blocked"
    assert pol.blocked_rule == "already_recovered"


def test_rule2_opted_out_customer_is_blocked():
    """Rule 2: Opted-out customers must never receive automated recovery action."""
    diag = _sample_diagnosis()
    pol = evaluate_policy(
        payment_id="pay_test_02",
        failure_category="soft_decline",
        amount=1000.0,
        attempt_count=1,
        opted_out=True,
        consent_for_voice=True,
        current_status="pending",
        diagnosis=diag,
        run_id="run_01",
    )
    assert pol.decision == "blocked"
    assert pol.blocked_rule == "customer_opted_out"


def test_rule3_hard_decline_is_blocked_no_retry():
    """Rule 3: Hard declines (fraud, stolen, invalid) must never be retried."""
    diag = _sample_diagnosis(cat="hard_decline", action="stop_no_retry")
    pol = evaluate_policy(
        payment_id="pay_test_03",
        failure_category="hard_decline",
        amount=2500.0,
        attempt_count=1,
        opted_out=False,
        consent_for_voice=False,
        current_status="pending",
        diagnosis=diag,
        run_id="run_01",
    )
    assert pol.decision == "blocked"
    assert pol.blocked_rule == "hard_decline_no_retry"


def test_rule4_max_retries_exhausted_is_blocked():
    """Rule 4: Payments with attempt_count >= 3 must be blocked."""
    diag = _sample_diagnosis()
    pol = evaluate_policy(
        payment_id="pay_test_04",
        failure_category="soft_decline",
        amount=1500.0,
        attempt_count=3,
        opted_out=False,
        consent_for_voice=True,
        current_status="pending",
        diagnosis=diag,
        run_id="run_01",
    )
    assert pol.decision == "blocked"
    assert pol.blocked_rule == "max_retries_reached"


def test_rule5_high_value_transaction_is_escalated():
    """Rule 5: Amounts > ₹25,000 must escalate to human manual review."""
    diag = _sample_diagnosis()
    pol = evaluate_policy(
        payment_id="pay_test_05",
        failure_category="soft_decline",
        amount=55000.0,
        attempt_count=1,
        opted_out=False,
        consent_for_voice=True,
        current_status="pending",
        diagnosis=diag,
        run_id="run_01",
    )
    assert pol.decision == "escalated"
    assert pol.selected_action == "manual_review"
    assert pol.escalation_reason == "high_value_threshold"


def test_rule6_low_confidence_ai_is_escalated():
    """Rule 6: Low AI confidence (< 0.6) escalates to human review rather than acting blindly."""
    diag = _sample_diagnosis(conf=0.45)
    pol = evaluate_policy(
        payment_id="pay_test_06",
        failure_category="soft_decline",
        amount=2000.0,
        attempt_count=1,
        opted_out=False,
        consent_for_voice=True,
        current_status="pending",
        diagnosis=diag,
        run_id="run_01",
    )
    assert pol.decision == "escalated"
    assert pol.selected_action == "manual_review"
    assert pol.escalation_reason == "low_confidence"


def test_rule7_voice_consent_suppresses_voice_channel():
    """Rule 7: Actions involving voice are modified/downgraded if consent is absent."""
    diag = _sample_diagnosis(
        cat="subscription_failed",
        action="retry_plus_reminder",
    )
    pol = evaluate_policy(
        payment_id="pay_test_07",
        failure_category="subscription_failed",
        amount=1499.0,
        attempt_count=1,
        opted_out=False,
        consent_for_voice=False,  # No voice consent
        current_status="pending",
        diagnosis=diag,
        run_id="run_01",
    )
    assert pol.decision == "modified"
    assert pol.selected_action == "retry_later"
    assert pol.idempotency_key is not None


def test_rule8_standard_approved_action():
    """Rule 8: Clean transaction with valid policy passes through approved."""
    diag = _sample_diagnosis(cat="soft_decline", conf=0.88, action="retry_later")
    pol = evaluate_policy(
        payment_id="pay_test_08",
        failure_category="soft_decline",
        amount=3499.0,
        attempt_count=1,
        opted_out=False,
        consent_for_voice=True,
        current_status="pending",
        diagnosis=diag,
        run_id="run_01",
    )
    assert pol.decision == "approved"
    assert pol.selected_action == "retry_later"
    assert pol.idempotency_key.startswith("idem_")


# ── 2. IDEMPOTENCY KEY TESTS ──────────────────────────────────────────────────

def test_idempotency_key_deterministic_and_unique():
    k1 = _make_idempotency_key("pay_01", "retry_later", "batch_1")
    k2 = _make_idempotency_key("pay_01", "retry_later", "batch_1")
    k3 = _make_idempotency_key("pay_01", "retry_later", "batch_2")
    assert k1 == k2
    assert k1 != k3


# ── 3. DIAGNOSIS ENGINE TESTS ─────────────────────────────────────────────────

def test_diagnosis_demo_all_six_categories():
    categories = [
        "soft_decline", "insufficient_funds", "hard_decline",
        "authentication_failed", "checkout_abandoned", "subscription_failed"
    ]
    for cat in categories:
        res = run_demo_diagnosis("pay_random", cat)
        assert res.diagnosis == cat
        assert 0.0 <= res.confidence <= 1.0
        assert res.recommended_action is not None
        assert res.risk_level in {"low", "medium", "high"}


# ── 4. RECOVERY SIMULATION TESTS ──────────────────────────────────────────────

def test_simulate_recovery_blocked():
    pol = PolicyOutput(decision="blocked", selected_action="stop_no_retry", reason="hard_decline")
    res = simulate_recovery("pay_01", 5000.0, "recovered", pol)
    assert res["final_status"] == "blocked"
    assert res["recovered_amount"] == 0.0


def test_simulate_recovery_approved_success():
    pol = PolicyOutput(decision="approved", selected_action="retry_later", reason="ok")
    res = simulate_recovery("pay_01", 5000.0, "recovered", pol)
    assert res["final_status"] == "recovered"
    assert res["recovered_amount"] == 5000.0


def test_simulate_blind_retry_eligibility():
    # Hard decline never recovered in blind retry
    r_hard = simulate_blind_retry("pay_HD001", "hard_decline", 2000.0, 1, False)
    assert r_hard["blind_retry_recovered"] is False

    # Max retries skipped in blind retry
    r_max = simulate_blind_retry("pay_SD001", "soft_decline", 2000.0, 3, False)
    assert r_max["blind_retry_recovered"] is False

    # Opted out skipped in blind retry
    r_opt = simulate_blind_retry("pay_SD001", "soft_decline", 2000.0, 1, True)
    assert r_opt["blind_retry_recovered"] is False

    # Known recoverable in seed set
    r_win = simulate_blind_retry("pay_SD001", "soft_decline", 4999.0, 1, False)
    assert r_win["blind_retry_recovered"] is True
    assert r_win["blind_retry_amount"] == 4999.0


# ── 5. API ENDPOINT & RAZORPAY WEBHOOK INTEGRATION TESTS ──────────────────────

def test_api_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["mode"] in {"DEMO_MODE", "LIVE_AI_MODE"}


def test_api_seed_and_payments(client):
    res = client.post("/api/seed")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in {"seeded", "already_seeded"}

    res_p = client.get("/api/payments")
    assert res_p.status_code == 200
    payments = res_p.json()
    assert len(payments) >= 50


def test_api_run_batch_and_metrics(client):
    res = client.post("/api/run-batch")
    assert res.status_code == 200
    data = res.json()
    assert "metrics" in data
    metrics = data["metrics"]
    assert metrics["total_payments"] >= 50
    assert metrics["ai_recovered_count"] > metrics["blind_retry_recovered_count"]
    assert metrics["ai_uplift_amount"] > 0
    assert metrics["blocked_actions"] > 0

    # Test payment audit trail
    first_id = data["payments"][0]["payment_id"]
    res_audit = client.get(f"/api/payments/{first_id}/audit")
    assert res_audit.status_code == 200
    audit_trail = res_audit.json()
    assert len(audit_trail) >= 5


def test_razorpay_webhook_ingestion(client):
    """Test Razorpay payment.failed webhook event ingestion."""
    payload = {
        "entity": "event",
        "account_id": "acc_razorpay_demo",
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_rzp_test_hook",
                    "amount": 499900,  # 4999.00 in paise
                    "currency": "INR",
                    "status": "failed",
                    "method": "upi",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": "Bank network timeout occurred during authorization",
                    "error_reason": "bank_timeout",
                    "notes": {
                        "customer_name": "Kavita Rao"
                    }
                }
            }
        }
    }
    res = client.post("/api/webhooks/razorpay", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "processed"
    assert data["payment_id"] == "pay_rzp_test_hook"
    assert data["category"] == "soft_decline"
    assert data["policy_decision"] in {"approved", "modified", "escalated", "blocked"}
    assert data["idempotency_key"] is not None
