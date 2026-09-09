"""
RecoverIQ — FastAPI Backend
All 8 API endpoints for the revenue recovery dashboard.

Endpoint summary:
  GET  /health
  POST /api/seed
  POST /api/run-batch
  GET  /api/payments
  GET  /api/payments/{payment_id}
  GET  /api/payments/{payment_id}/audit
  GET  /api/metrics
  GET  /api/audio-sample
"""
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .database import get_db, create_tables
from .models import Payment, AuditLog, BatchRun
from .schemas import PaymentOut, MetricsOut, AuditEntry, BatchRunOut
from .seed import get_seed_payments
from .diagnosis import diagnose
from .policy import evaluate_policy
from .recovery import simulate_recovery, simulate_blind_retry
from .audit import (
    log_ingestion, log_diagnosis, log_policy,
    log_idempotency_key, log_recovery_simulated, log_result, log_blind_retry,
)
from .metrics import compute_metrics
from .config import settings

app = FastAPI(
    title="RecoverIQ API",
    description="Policy-gated AI revenue recovery — demo backend",
    version="1.0.0",
)

allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
else:
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    create_tables()


# ── GET /health ────────────────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "mode": "DEMO_MODE" if settings.demo_mode else "LIVE_AI_MODE",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
    }


# ── POST /api/seed ─────────────────────────────────────────────────────────────
@app.post("/api/seed")
def seed_payments(db: Session = Depends(get_db)):
    """Seed 50 synthetic payments. Idempotent — skips if already seeded."""
    existing = db.query(Payment).count()
    if existing >= 50:
        return {"status": "already_seeded", "count": existing}

    seed_data = get_seed_payments()
    for p in seed_data:
        payment = Payment(**p)
        payment.status = "pending"
        db.add(payment)

    db.commit()
    return {"status": "seeded", "count": len(seed_data)}


# ── POST /api/run-batch ────────────────────────────────────────────────────────
@app.post("/api/run-batch")
async def run_batch(db: Session = Depends(get_db)):
    """
    Run the full recovery pipeline on all payments.
    Idempotent: resets all payment results and audit logs before re-running.
    Steps per payment:
      1. Reset state
      2. AI diagnosis (cached in DEMO_MODE)
      3. Policy evaluation (deterministic rules)
      4. Recovery simulation (uses hidden_recovery_outcome)
      5. Blind retry baseline comparison
      6. Audit log (7 entries per payment)
    """
    # Auto-seed if not seeded
    existing = db.query(Payment).count()
    if existing == 0:
        seed_data = get_seed_payments()
        for p in seed_data:
            payment = Payment(**p)
            payment.status = "pending"
            db.add(payment)
        db.flush()

    # Create a new batch run ID
    run_id = f"batch_{uuid.uuid4().hex[:8]}"

    # Clear previous batch results (audit logs + payment results)
    db.query(AuditLog).delete()
    payments = db.query(Payment).all()
    for p in payments:
        p.status = "pending"
        p.ai_diagnosis = None
        p.ai_confidence = None
        p.ai_reasoning = None
        p.ai_recommended_action = None
        p.ai_risk_level = None
        p.policy_decision = None
        p.policy_selected_action = None
        p.policy_reason = None
        p.policy_idempotency_key = None
        p.policy_blocked_rule = None
        p.policy_escalation_reason = None
        p.action_taken = None
        p.final_status = None
        p.recovered_amount = 0.0
        p.blind_retry_recovered = False
        p.blind_retry_amount = 0.0
        p.batch_run_id = run_id
    db.flush()

    mode = "DEMO_MODE" if settings.demo_mode else "LIVE_AI_MODE"

    for p in payments:
        provenance = getattr(p, "provenance", None) or "SEEDED_DEMO"
        # Step 1 — Audit: ingestion
        log_ingestion(db, p.payment_id, p.amount, p.failure_category, run_id, provenance=provenance)

        # Step 2 — Diagnosis
        payment_dict = {
            "payment_id": p.payment_id,
            "failure_category": p.failure_category,
            "failure_code": p.failure_code,
            "failure_message": p.failure_message,
            "amount": p.amount,
            "payment_method": p.payment_method,
            "attempt_count": p.attempt_count,
            "customer_name": p.customer_name,
            "provenance": provenance,
        }
        diagnosis = await diagnose(p.payment_id, p.failure_category, payment_dict, provenance=provenance)
        p.ai_diagnosis = diagnosis.diagnosis
        p.ai_confidence = diagnosis.confidence
        p.ai_reasoning = diagnosis.reasoning_summary
        p.ai_recommended_action = diagnosis.recommended_action
        p.ai_risk_level = diagnosis.risk_level
        log_diagnosis(db, p.payment_id, diagnosis, mode, run_id, provenance=provenance)

        # Step 3 — Policy evaluation
        policy = evaluate_policy(
            payment_id=p.payment_id,
            failure_category=p.failure_category,
            amount=p.amount,
            attempt_count=p.attempt_count,
            opted_out=p.opted_out,
            consent_for_voice=p.consent_for_voice,
            current_status=p.status,
            diagnosis=diagnosis,
            run_id=run_id,
        )
        p.policy_decision = policy.decision
        p.policy_selected_action = policy.selected_action
        p.policy_reason = policy.reason
        p.policy_idempotency_key = policy.idempotency_key
        p.policy_blocked_rule = policy.blocked_rule
        p.policy_escalation_reason = policy.escalation_reason
        log_policy(db, p.payment_id, policy, run_id)

        # Step 4 — Idempotency key (if action approved/modified)
        if policy.idempotency_key:
            log_idempotency_key(
                db, p.payment_id, policy.idempotency_key,
                policy.selected_action, run_id
            )

        # Step 5 — Recovery simulation
        log_recovery_simulated(db, p.payment_id, policy.selected_action, run_id)
        result = simulate_recovery(
            payment_id=p.payment_id,
            amount=p.amount,
            hidden_recovery_outcome=p.hidden_recovery_outcome,
            policy=policy,
        )
        p.action_taken = result["action_taken"]
        p.final_status = result["final_status"]
        p.recovered_amount = result["recovered_amount"]
        p.status = result["final_status"]
        log_result(db, p.payment_id, result["final_status"], result["recovered_amount"], run_id)

        # Step 6 — Blind retry baseline
        blind = simulate_blind_retry(
            payment_id=p.payment_id,
            failure_category=p.failure_category,
            amount=p.amount,
            attempt_count=p.attempt_count,
            opted_out=p.opted_out,
        )
        p.blind_retry_recovered = blind["blind_retry_recovered"]
        p.blind_retry_amount = blind["blind_retry_amount"]
        log_blind_retry(
            db, p.payment_id,
            blind["blind_retry_recovered"], blind["blind_retry_amount"], run_id
        )

    # Save batch run record
    batch = db.query(BatchRun).filter(BatchRun.run_id == run_id).first()
    if not batch:
        batch = BatchRun(run_id=run_id, mode=mode)
        db.add(batch)

    db.commit()
    db.refresh(batch)

    # Compute metrics
    metrics = compute_metrics(db, mode)

    # Refresh payments for response
    payments = db.query(Payment).all()
    return {
        "run_id": run_id,
        "mode": mode,
        "payments": [PaymentOut.model_validate(p) for p in payments],
        "metrics": metrics,
    }


# ── GET /api/payments ──────────────────────────────────────────────────────────
@app.get("/api/payments", response_model=list[PaymentOut])
def get_payments(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Returns all payments. Optional ?status= filter.
    Supported status values: recovered, not_recovered, blocked,
    escalated, needs_customer_action, unresolved, pending
    """
    q = db.query(Payment)
    if status:
        q = q.filter(Payment.final_status == status)
    return q.all()


# ── GET /api/payments/{payment_id} ────────────────────────────────────────────
@app.get("/api/payments/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: str, db: Session = Depends(get_db)):
    p = db.query(Payment).filter(Payment.payment_id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    return p


# ── GET /api/payments/{payment_id}/audit ──────────────────────────────────────
@app.get("/api/payments/{payment_id}/audit", response_model=list[AuditEntry])
def get_audit(payment_id: str, db: Session = Depends(get_db)):
    entries = (
        db.query(AuditLog)
        .filter(AuditLog.payment_id == payment_id)
        .order_by(AuditLog.timestamp)
        .all()
    )
    return [
        AuditEntry(
            id=e.id,
            payment_id=e.payment_id,
            batch_run_id=e.batch_run_id,
            timestamp=e.timestamp,
            actor=e.actor,
            event_type=e.event_type,
            message=e.message,
            metadata=e.metadata_,
        )
        for e in entries
    ]


# ── GET /api/metrics ──────────────────────────────────────────────────────────
@app.get("/api/metrics", response_model=MetricsOut)
def get_metrics(db: Session = Depends(get_db)):
    mode = "DEMO_MODE" if settings.demo_mode else "LIVE_AI_MODE"
    return compute_metrics(db, mode)


# ── GET /api/audio-sample ─────────────────────────────────────────────────────
@app.get("/api/audio-sample")
def get_audio_sample():
    """
    Returns metadata for the Hinglish recovery nudge audio card.
    No live audio generation. This is a cached demo nudge.
    No real phone call is made.
    """
    return {
        "title": "Hinglish Recovery Nudge",
        "case_context": (
            "Customer: Rahul Sharma | Payment: pay_AF001 | Amount: ₹2,499 | "
            "Failure: 3DS authentication failed | Locale: hi-IN | "
            "Voice consent: Yes"
        ),
        "transcript": (
            "Hi Rahul, aapka ₹2,499 ka payment complete nahi ho paya "
            "kyunki bank authentication fail ho gaya. Aap secure payment "
            "link se payment dobara complete kar sakte hain. Yeh reminder "
            "sirf ek baar bheja gaya hai. Dhanyavaad."
        ),
        "audio_file": "/demo-audio.wav",
        "disclaimer": (
            "This is a cached demo nudge for presentation purposes only. "
            "No real phone call was made. No real message was sent. "
            "In production, voice reminders would only be sent with "
            "explicit customer consent and via a compliant telephony API."
        ),
        "language": "Hinglish (Hindi + English)",
        "duration_seconds": 14,
        "generated_at": "2026-08-29T10:00:00+05:30",
        "is_live": False,
    }


# ── POST /api/webhooks/razorpay ───────────────────────────────────────────────
@app.post("/api/webhooks/razorpay")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Ingest real or simulated Razorpay webhook events (e.g. payment.failed).
    Parses payload, maps error codes to RecoverIQ failure categories,
    evaluates policy engine rules deterministically, logs audit entries,
    and returns immediate policy decision & recovery status.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event = payload.get("event", "payment.failed")
    payment_entity = (
        payload.get("payload", {})
        .get("payment", {})
        .get("entity", {})
    )
    if not payment_entity:
        payment_entity = payload

    raw_id = payment_entity.get("id") or f"pay_rzp_{uuid.uuid4().hex[:6]}"
    raw_amount = payment_entity.get("amount", 2500.0)
    # Razorpay transmits amounts in paise (integers)
    amount = float(raw_amount / 100.0 if isinstance(raw_amount, int) and raw_amount > 100 else raw_amount)
    payment_method = payment_entity.get("method", "upi")
    err_desc = str(payment_entity.get("error_description", "")).lower()
    err_code = str(payment_entity.get("error_code", "PAYMENT_FAILED"))
    err_reason = str(payment_entity.get("error_reason", "")).lower()

    # Map Razorpay error indicators to RecoverIQ failure categories
    if any(k in err_desc or k in err_reason for k in ["timeout", "gateway_error", "issuer_down", "server_error"]):
        cat = "soft_decline"
    elif any(k in err_desc or k in err_reason for k in ["otp", "3ds", "authentication", "verification", "pin"]):
        cat = "authentication_failed"
    elif any(k in err_desc or k in err_reason for k in ["insufficient", "balance", "funds"]):
        cat = "insufficient_funds"
    elif any(k in err_desc or k in err_reason for k in ["fraud", "stolen", "lost", "blocked", "blacklisted"]):
        cat = "hard_decline"
    elif any(k in err_desc or k in err_reason for k in ["mandate", "recurring", "subscription"]):
        cat = "subscription_failed"
    elif any(k in err_desc or k in err_reason for k in ["cancel", "drop", "abandon"]):
        cat = "checkout_abandoned"
    else:
        cat = "soft_decline"

    # Check if payment already exists in DB
    existing = db.query(Payment).filter(Payment.payment_id == raw_id).first()
    run_id = f"rzp_hook_{uuid.uuid4().hex[:8]}"

    if not existing:
        customer_name = (
            payment_entity.get("notes", {}).get("customer_name")
            or payment_entity.get("customer_name")
            or "Razorpay Customer"
        )
        existing = Payment(
            payment_id=raw_id,
            customer_id=payment_entity.get("customer_id", f"cust_{raw_id[-4:]}"),
            customer_name=customer_name,
            amount=amount,
            currency=payment_entity.get("currency", "INR"),
            payment_method=payment_method,
            failure_category=cat,
            failure_code=err_code,
            failure_message=payment_entity.get("error_description") or "Payment failed via Razorpay",
            attempt_count=1,
            customer_locale="en-IN",
            consent_for_voice=False,
            opted_out=False,
            created_at=datetime.now(),
            last_attempt_at=datetime.now(),
            hidden_recovery_outcome="recovered" if cat in {"soft_decline", "insufficient_funds", "checkout_abandoned"} else "not_recovered",
            status="pending",
            provenance="RAZORPAY_WEBHOOK",
        )
        db.add(existing)
        db.flush()
    else:
        existing.provenance = "RAZORPAY_WEBHOOK"

    # Ingestion audit
    log_ingestion(db, existing.payment_id, existing.amount, existing.failure_category, run_id, provenance="RAZORPAY_WEBHOOK")

    # Diagnosis
    payment_dict = {
        "payment_id": existing.payment_id,
        "failure_category": existing.failure_category,
        "failure_code": existing.failure_code,
        "failure_message": existing.failure_message,
        "amount": existing.amount,
        "payment_method": existing.payment_method,
        "attempt_count": existing.attempt_count,
        "customer_name": existing.customer_name,
        "provenance": "RAZORPAY_WEBHOOK",
    }
    diagnosis = await diagnose(existing.payment_id, existing.failure_category, payment_dict, provenance="RAZORPAY_WEBHOOK")
    existing.ai_diagnosis = diagnosis.diagnosis
    existing.ai_confidence = diagnosis.confidence
    existing.ai_reasoning = diagnosis.reasoning_summary
    existing.ai_recommended_action = diagnosis.recommended_action
    existing.ai_risk_level = diagnosis.risk_level
    log_diagnosis(db, existing.payment_id, diagnosis, "DEMO_MODE", run_id, provenance="RAZORPAY_WEBHOOK")

    # Policy evaluation
    policy = evaluate_policy(
        payment_id=existing.payment_id,
        failure_category=existing.failure_category,
        amount=existing.amount,
        attempt_count=existing.attempt_count,
        opted_out=existing.opted_out,
        consent_for_voice=existing.consent_for_voice,
        current_status=existing.status,
        diagnosis=diagnosis,
        run_id=run_id,
    )
    existing.policy_decision = policy.decision
    existing.policy_selected_action = policy.selected_action
    existing.policy_reason = policy.reason
    existing.policy_idempotency_key = policy.idempotency_key
    existing.policy_blocked_rule = policy.blocked_rule
    existing.policy_escalation_reason = policy.escalation_reason
    log_policy(db, existing.payment_id, policy, run_id)

    if policy.idempotency_key:
        log_idempotency_key(db, existing.payment_id, policy.idempotency_key, policy.selected_action, run_id)

    log_recovery_simulated(db, existing.payment_id, policy.selected_action, run_id)
    result = simulate_recovery(
        payment_id=existing.payment_id,
        amount=existing.amount,
        hidden_recovery_outcome=existing.hidden_recovery_outcome,
        policy=policy,
    )
    existing.action_taken = result["action_taken"]
    existing.final_status = result["final_status"]
    existing.recovered_amount = result["recovered_amount"]
    existing.status = result["final_status"]
    log_result(db, existing.payment_id, result["final_status"], result["recovered_amount"], run_id)

    db.commit()
    db.refresh(existing)

    return {
        "status": "processed",
        "event": event,
        "payment_id": existing.payment_id,
        "category": cat,
        "policy_decision": policy.decision,
        "selected_action": policy.selected_action,
        "idempotency_key": policy.idempotency_key,
        "recovery_status": existing.final_status,
        "recovered_amount": existing.recovered_amount,
    }

