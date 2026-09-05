"""
Deterministic Policy Engine.

Rules (in evaluation order):
 1. Stop if already recovered
 2. Block if customer opted out
 3. Block if hard_decline (no retry ever)
 4. Block if max retries (3) exhausted
 5. Escalate if amount > ₹25,000 (high-value threshold)
 6. Escalate if AI confidence < 0.6 (low-confidence routing signal)
 7. Modify: remove voice reminder if consent_for_voice is False
 8. Approve the recommended action

The policy engine never executes actions — it only decides and records reasons.
Every approved/modified action carries an idempotency key.
Every block/escalation records a clear rule name in the audit log.
"""
import hashlib
import time
from datetime import datetime
from .schemas import DiagnosisOutput, PolicyOutput
from .config import settings

RETRYABLE_CATEGORIES = {"soft_decline", "subscription_failed"}
VOICE_ACTIONS = {"customer_action_reminder", "reminder_message", "retry_plus_reminder"}


def _make_idempotency_key(payment_id: str, action: str, run_id: str) -> str:
    """Deterministic idempotency key: sha256(payment_id + action + run_id)[:24]."""
    raw = f"{payment_id}:{action}:{run_id}"
    return "idem_" + hashlib.sha256(raw.encode()).hexdigest()[:20]


def evaluate_policy(
    payment_id: str,
    failure_category: str,
    amount: float,
    attempt_count: int,
    opted_out: bool,
    consent_for_voice: bool,
    current_status: str,
    diagnosis: DiagnosisOutput,
    run_id: str,
) -> PolicyOutput:
    """
    Evaluate all policy rules deterministically and return a PolicyOutput.
    Rules are evaluated in priority order — first match wins.
    """

    # Rule 1 — Stop if already recovered (idempotency guard)
    if current_status == "recovered":
        return PolicyOutput(
            decision="blocked",
            selected_action="stop_no_retry",
            reason="Payment already recovered. No further action needed.",
            blocked_rule="already_recovered",
        )

    # Rule 2 — Block if customer opted out
    if opted_out:
        return PolicyOutput(
            decision="blocked",
            selected_action="stop_no_retry",
            reason="Customer has opted out of recovery communications. No action permitted.",
            blocked_rule="customer_opted_out",
        )

    # Rule 3 — Block if hard_decline (permanent failure)
    if failure_category == "hard_decline":
        return PolicyOutput(
            decision="blocked",
            selected_action="stop_no_retry",
            reason=(
                "Hard decline detected (blocked/invalid card or suspected fraud). "
                "Retrying would be futile and potentially harmful. Policy mandates stop."
            ),
            blocked_rule="hard_decline_no_retry",
        )

    # Rule 4 — Block if max retries exhausted
    if attempt_count >= settings.max_retries:
        return PolicyOutput(
            decision="blocked",
            selected_action="stop_no_retry",
            reason=(
                f"Payment has reached maximum retry limit ({settings.max_retries}). "
                "Further automated retries are not permitted."
            ),
            blocked_rule="max_retries_reached",
        )

    # Rule 5 — Escalate if high-value transaction (> ₹25,000)
    if amount > settings.high_value_threshold:
        return PolicyOutput(
            decision="escalated",
            selected_action="manual_review",
            reason=(
                f"Transaction amount ₹{amount:,.0f} exceeds high-value threshold "
                f"of ₹{settings.high_value_threshold:,.0f}. "
                "Escalating to manual review to prevent automated risk."
            ),
            escalation_reason="high_value_threshold",
        )

    # Rule 6 — Escalate if AI confidence below threshold
    if diagnosis.confidence < settings.low_confidence_threshold:
        return PolicyOutput(
            decision="escalated",
            selected_action="manual_review",
            reason=(
                f"AI diagnosis confidence {diagnosis.confidence:.0%} is below "
                f"the routing threshold of {settings.low_confidence_threshold:.0%}. "
                "Escalating to manual review rather than acting on uncertain diagnosis."
            ),
            escalation_reason="low_confidence",
        )

    # Rule 7 — Modify: strip voice from action if consent not given
    selected_action = diagnosis.recommended_action
    modified = False
    modify_note = ""

    if selected_action in VOICE_ACTIONS and not consent_for_voice:
        # Downgrade to non-voice equivalent
        if selected_action == "customer_action_reminder":
            selected_action = "customer_action_reminder"  # keep but no voice
        elif selected_action == "reminder_message":
            selected_action = "reminder_message"  # keep but no voice
        elif selected_action == "retry_plus_reminder":
            selected_action = "retry_later"  # strip reminder, keep retry
        modified = True
        modify_note = " Voice channel suppressed: customer has not given voice consent."

    # Rule 8 — Approve
    ikey = _make_idempotency_key(payment_id, selected_action, run_id)
    decision = "modified" if modified else "approved"
    reason = (
        f"All policy rules passed. Action '{selected_action}' approved for execution. "
        f"Diagnosis: {diagnosis.diagnosis} (confidence {diagnosis.confidence:.0%}), "
        f"risk level: {diagnosis.risk_level}."
        + modify_note
    )

    return PolicyOutput(
        decision=decision,
        selected_action=selected_action,
        reason=reason,
        idempotency_key=ikey,
    )
