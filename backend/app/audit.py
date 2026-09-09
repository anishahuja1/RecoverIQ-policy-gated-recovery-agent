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
from datetime import datetime
from sqlalchemy.orm import Session
from .models import AuditLog


def log(
    db: Session,
    payment_id: str,
    actor: str,
    event_type: str,
    message: str,
    batch_run_id: str | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    """Append a single audit entry to the database."""
    entry = AuditLog(
        payment_id=payment_id,
        batch_run_id=batch_run_id,
        timestamp=datetime.now(),
        actor=actor,
        event_type=event_type,
        message=message,
        metadata_=metadata or {},
    )
    db.add(entry)
    db.flush()  # get the id without committing
    return entry


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
