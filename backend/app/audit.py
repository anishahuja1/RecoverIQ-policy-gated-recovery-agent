"""
Audit Logger.

Every payment gets a timestamped audit trail explaining WHY each step happened,
not just what happened. Each entry has: timestamp, actor, event_type, message, metadata.

Actors:
  system              — ingestion, batch management
  diagnosis_engine    — AI/cached diagnosis
  policy_engine       — rule evaluation
  recovery_executor   — action simulation
  baseline_simulator  — blind retry comparison
"""
import hashlib
import json
from datetime import datetime
from sqlalchemy.orm import Session
from .models import AuditLog


def compute_event_hash(
    prev_hash: str | None,
    payment_id: str,
    actor: str,
    event_type: str,
    message: str,
    timestamp_str: str,
) -> str:
    """Computes deterministic SHA-256 hash over canonically serialized audit payload."""
    prev = prev_hash or "GENESIS"
    canonical_payload = json.dumps(
        {
            "actor": actor,
            "event_type": event_type,
            "message": message,
            "payment_id": payment_id,
            "timestamp": timestamp_str,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    raw = f"{prev}||{canonical_payload}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def log(
    db: Session,
    payment_id: str,
    actor: str,
    event_type: str,
    message: str,
    batch_run_id: str | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    """Append a single cryptographically chained audit entry to the database."""
    now = datetime.now()
    now_str = now.isoformat()

    last_log = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    prev_hash = last_log.event_hash if (last_log and last_log.event_hash) else "GENESIS"
    event_hash = compute_event_hash(prev_hash, payment_id, actor, event_type, message, now_str)

    entry = AuditLog(
        payment_id=payment_id,
        batch_run_id=batch_run_id,
        timestamp=now,
        actor=actor,
        event_type=event_type,
        message=message,
        metadata_=metadata or {},
        prev_hash=prev_hash,
        event_hash=event_hash,
    )
    db.add(entry)
    db.flush()  # get the id without committing
    return entry


def verify_audit_chain(db: Session, payment_id: str | None = None) -> dict:
    """
    Traverses and verifies the SHA-256 tamper-evident hash chain.
    Detects any altered payloads, broken links, inserted, or deleted rows.
    """
    query = db.query(AuditLog).order_by(AuditLog.id.asc())
    if payment_id:
        query = query.filter(AuditLog.payment_id == payment_id)
    rows = query.all()

    if not rows:
        return {
            "is_valid": True,
            "total_verified": 0,
            "broken_at_id": None,
            "message": "Audit chain is empty.",
        }

    for i, row in enumerate(rows):
        expected_hash = compute_event_hash(
            row.prev_hash,
            row.payment_id,
            row.actor,
            row.event_type,
            row.message,
            row.timestamp.isoformat(),
        )
        if row.event_hash != expected_hash:
            return {
                "is_valid": False,
                "total_verified": i,
                "broken_at_id": row.id,
                "message": (
                    f"Tampered entry detected at audit log ID {row.id} (payment {row.payment_id}). "
                    f"Stored hash does not match recomputed hash."
                ),
            }

        if payment_id is None and i > 0:
            prev_row = rows[i - 1]
            if row.prev_hash != prev_row.event_hash:
                return {
                    "is_valid": False,
                    "total_verified": i,
                    "broken_at_id": row.id,
                    "message": (
                        f"Broken chain link detected at audit log ID {row.id}. "
                        f"Previous hash does not link to preceding event hash."
                    ),
                }

    return {
        "is_valid": True,
        "total_verified": len(rows),
        "broken_at_id": None,
        "message": f"Cryptographic audit chain intact. Verified {len(rows)} sequential events.",
    }


def log_ingestion(db: Session, payment_id: str, amount: float,
                  failure_category: str, batch_run_id: str,
                  provenance: str = "SEEDED_DEMO") -> None:
    log(
        db, payment_id,
        actor="system",
        event_type="payment_ingested",
        message=(
            f"Payment {payment_id} ingested [provenance: {provenance}]. "
            f"Amount: ₹{amount:,.2f}. Failure category: {failure_category}. "
            "Queued for AI diagnosis."
        ),
        batch_run_id=batch_run_id,
        metadata={"amount": amount, "failure_category": failure_category, "provenance": provenance},
    )


def log_diagnosis(db: Session, payment_id: str, diagnosis, mode: str,
                  batch_run_id: str, provenance: str = "SEEDED_DEMO") -> None:
    log(
        db, payment_id,
        actor="diagnosis_engine",
        event_type="diagnosis_generated",
        message=(
            f"{'Cached demo' if mode == 'DEMO_MODE' else 'Live AI'} diagnosis generated [provenance: {provenance}]: "
            f"{diagnosis.diagnosis}, confidence {diagnosis.confidence:.0%}. "
            f"Reasoning: {diagnosis.reasoning_summary} "
            f"Recommended action: {diagnosis.recommended_action}. "
            f"Risk level: {diagnosis.risk_level}."
        ),
        batch_run_id=batch_run_id,
        metadata={
            "diagnosis": diagnosis.diagnosis,
            "confidence": diagnosis.confidence,
            "recommended_action": diagnosis.recommended_action,
            "risk_level": diagnosis.risk_level,
            "mode": mode,
            "provenance": provenance,
        },
    )


def log_policy(db: Session, payment_id: str, policy, batch_run_id: str) -> None:
    log(
        db, payment_id,
        actor="policy_engine",
        event_type="policy_evaluated",
        message=(
            f"Policy decision: {policy.decision.upper()}. "
            f"Selected action: {policy.selected_action}. "
            f"Reason: {policy.reason}"
            + (f" Blocked rule: {policy.blocked_rule}." if policy.blocked_rule else "")
            + (f" Escalation reason: {policy.escalation_reason}." if policy.escalation_reason else "")
        ),
        batch_run_id=batch_run_id,
        metadata={
            "decision": policy.decision,
            "selected_action": policy.selected_action,
            "blocked_rule": policy.blocked_rule,
            "escalation_reason": policy.escalation_reason,
        },
    )


def log_idempotency_key(db: Session, payment_id: str, ikey: str,
                        action: str, batch_run_id: str) -> None:
    log(
        db, payment_id,
        actor="recovery_executor",
        event_type="idempotency_key_generated",
        message=(
            f"Idempotency key generated for action '{action}': {ikey}. "
            "This ensures the recovery action is executed exactly once, "
            "even if the system retries the request."
        ),
        batch_run_id=batch_run_id,
        metadata={"idempotency_key": ikey, "action": action},
    )


def log_recovery_simulated(db: Session, payment_id: str, action: str,
                            batch_run_id: str) -> None:
    log(
        db, payment_id,
        actor="recovery_executor",
        event_type="recovery_simulated",
        message=(
            f"Recovery action '{action}' executed in simulation/test mode. "
            "No real charges made. No real messages sent. "
            "This is a bounded, simulated recovery action for demo purposes."
        ),
        batch_run_id=batch_run_id,
        metadata={"action": action, "mode": "simulation"},
    )


def log_result(db: Session, payment_id: str, final_status: str,
               recovered_amount: float, batch_run_id: str) -> None:
    if recovered_amount > 0:
        outcome_msg = (
            f"Recovery SUCCESSFUL. Simulated/test-mode recovered revenue: "
            f"₹{recovered_amount:,.2f}. Final status: {final_status}."
        )
    elif final_status == "blocked":
        outcome_msg = (
            f"Recovery BLOCKED by policy engine. No action taken. "
            f"Final status: {final_status}. Recovered: ₹0."
        )
    elif final_status == "escalated":
        outcome_msg = (
            f"Payment ESCALATED to manual review. Automated recovery paused. "
            f"Final status: {final_status}. Recovered: ₹0."
        )
    elif final_status == "needs_customer_action":
        outcome_msg = (
            f"Recovery PENDING customer action. Reminder sent. "
            f"Awaiting customer response. Recovered: ₹0 so far."
        )
    else:
        outcome_msg = (
            f"Recovery attempt completed. Final status: {final_status}. "
            f"Recovered: ₹{recovered_amount:,.2f}."
        )
    log(
        db, payment_id,
        actor="recovery_executor",
        event_type="result_recorded",
        message=outcome_msg,
        batch_run_id=batch_run_id,
        metadata={"final_status": final_status, "recovered_amount": recovered_amount},
    )


def log_blind_retry(db: Session, payment_id: str, recovered: bool,
                    amount: float, batch_run_id: str) -> None:
    if recovered:
        msg = (
            f"Blind retry baseline: payment recovered ₹{amount:,.2f} without AI guidance. "
            "Simple retry without personalization or diagnosis succeeded."
        )
    else:
        msg = (
            "Blind retry baseline: retry attempted without AI guidance. "
            "No recovery. Demonstrates uplift value of AI-guided policy."
        )
    log(
        db, payment_id,
        actor="baseline_simulator",
        event_type="blind_retry_simulated",
        message=msg,
        batch_run_id=batch_run_id,
        metadata={"blind_retry_recovered": recovered, "amount": amount if recovered else 0},
    )
