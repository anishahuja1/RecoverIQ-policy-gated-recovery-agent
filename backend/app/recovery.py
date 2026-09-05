"""
Recovery Executor (Simulator) + Blind Retry Baseline.

IMPORTANT: This is a pure simulator. No real charges are made.
           No real API calls to Razorpay production.
           No real phone calls or messages are sent.
           This module uses each payment's hidden_recovery_outcome to decide
           whether simulated recovery succeeds.

Recovery outcomes:
  recovered              → recovered_amount = payment.amount
  not_recovered          → recovered_amount = 0
  blocked                → recovered_amount = 0 (policy blocked it)
  escalated              → recovered_amount = 0 (manual review)
  needs_customer_action  → recovered_amount = 0 (awaiting customer)
  unresolved             → recovered_amount = 0 (no clear path)

Blind retry baseline:
  Retries soft_decline and subscription_failed records without AI/personalization.
  Recovers a subset using a deterministic lookup (no randomness, demo-safe).
  Performs meaningfully worse than AI policy — no personalized reminders, no escalation.
"""
from .schemas import PolicyOutput

# Payments that blind retry recovers (deterministic, demo-safe subset)
# Only soft_decline and subscription_failed are eligible.
# Hard declines never recovered. Auth/abandoned/insufficient not attempted.
BLIND_RETRY_RECOVERS: set[str] = {
    "pay_SD001",
    "pay_SD002",
    "pay_SD004",
    "pay_SD010",
    "pay_SF001",
    "pay_SF004",
}


def simulate_recovery(
    payment_id: str,
    amount: float,
    hidden_recovery_outcome: str,
    policy: PolicyOutput,
) -> dict:
    """
    Simulate recovery execution based on policy decision and hidden outcome.

    Returns a dict with:
      action_taken, final_status, recovered_amount
    """
    # If policy blocked or escalated, honor that — don't use hidden outcome
    if policy.decision == "blocked":
        return {
            "action_taken": policy.selected_action,
            "final_status": "blocked",
            "recovered_amount": 0.0,
        }

    if policy.decision == "escalated":
        return {
            "action_taken": "manual_review",
            "final_status": "escalated",
            "recovered_amount": 0.0,
        }

    # For approved/modified actions, use hidden_recovery_outcome
    outcome_map = {
        "recovered": ("recovered", amount),
        "not_recovered": ("not_recovered", 0.0),
        "needs_customer_action": ("needs_customer_action", 0.0),
        "unresolved": ("unresolved", 0.0),
        "escalated": ("escalated", 0.0),
        "blocked": ("blocked", 0.0),
    }

    final_status, recovered_amount = outcome_map.get(
        hidden_recovery_outcome, ("unresolved", 0.0)
    )

    return {
        "action_taken": policy.selected_action,
        "final_status": final_status,
        "recovered_amount": recovered_amount,
    }


def simulate_blind_retry(
    payment_id: str,
    failure_category: str,
    amount: float,
    attempt_count: int,
    opted_out: bool,
) -> dict:
    """
    Blind retry baseline: retries eligible payments without AI diagnosis or personalization.

    Rules:
    - Only retries soft_decline and subscription_failed
    - Skips opted_out customers
    - Skips if attempt_count >= 3
    - Never retries hard_decline
    - No personalized reminders
    - Recovers a deterministic subset (BLIND_RETRY_RECOVERS)
    """
    ELIGIBLE_CATEGORIES = {"soft_decline", "subscription_failed"}

    if opted_out:
        return {"blind_retry_recovered": False, "blind_retry_amount": 0.0}

    if failure_category not in ELIGIBLE_CATEGORIES:
        return {"blind_retry_recovered": False, "blind_retry_amount": 0.0}

    if attempt_count >= 3:
        return {"blind_retry_recovered": False, "blind_retry_amount": 0.0}

    if payment_id in BLIND_RETRY_RECOVERS:
        return {"blind_retry_recovered": True, "blind_retry_amount": amount}

    return {"blind_retry_recovered": False, "blind_retry_amount": 0.0}
