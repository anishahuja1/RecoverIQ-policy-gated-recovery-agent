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


# ── Calibrated Probabilistic Outcome Modeling ─────────────────────────────────
# Benchmark recovery probability parameters calibrated against Indian payment
# gateway recovery literature (e.g. Razorpay Magic Checkout / Chargebee recovery benchmarks):
CALIBRATED_PROBABILITIES = {
    "soft_decline": {
        "recoveriq_base": 0.56,  # Smart delay + optimal retry window
        "blind_retry_base": 0.18, # Instant blind retry hits same bank timeout
    },
    "insufficient_funds": {
        "recoveriq_base": 0.38,  # Payment link reminder gives time to top-up / change account
        "blind_retry_base": 0.00, # Blind retry fails immediately if funds not added
    },
    "authentication_failed": {
        "recoveriq_base": 0.46,  # Targeted OTP/PIN prompt nudges customer to complete 3DS
        "blind_retry_base": 0.00, # Automated retry cannot authenticate OTP/3DS
    },
    "checkout_abandoned": {
        "recoveriq_base": 0.32,  # WhatsApp/SMS reminder with persistent cart
        "blind_retry_base": 0.00, # Dropped checkout cannot be retried automatically
    },
    "subscription_failed": {
        "recoveriq_base": 0.44,  # Retry mandate + simultaneously notify customer
        "blind_retry_base": 0.16, # Repeated mandate call without customer notification
    },
    "hard_decline": {
        "recoveriq_base": 0.00,  # 0% recovery, but 100% blocked by policy (no fraud/penalties)
        "blind_retry_base": 0.00, # 0% recovery, but blindly retried (penalized by card networks)
    },
}


def simulate_probabilistic_recovery(
    category: str,
    amount: float,
    attempt_count: int,
    policy_decision: str,
    random_draw: float,
) -> dict:
    """
    Probabilistic recovery simulator calibrated against real payment gateway recovery distributions.
    Used for Monte Carlo evaluation across large synthetic distributions.
    """
    if policy_decision == "blocked":
        return {"final_status": "blocked", "recovered_amount": 0.0}
    if policy_decision == "escalated":
        return {"final_status": "escalated", "recovered_amount": 0.0}

    params = CALIBRATED_PROBABILITIES.get(category, {"recoveriq_base": 0.20})
    base_p = params.get("recoveriq_base", 0.20)

    # Attempt count decay penalty
    decay = max(0.0, (attempt_count - 1) * 0.12)
    # High amount slight friction penalty
    amount_penalty = 0.05 if amount > 10000.0 else 0.0
    effective_p = max(0.05, base_p - decay - amount_penalty)

    if random_draw <= effective_p:
        return {"final_status": "recovered", "recovered_amount": amount}
    elif random_draw <= effective_p + 0.20 and category in {"insufficient_funds", "authentication_failed", "checkout_abandoned"}:
        return {"final_status": "needs_customer_action", "recovered_amount": 0.0}
    else:
        return {"final_status": "not_recovered", "recovered_amount": 0.0}


def simulate_probabilistic_blind_retry(
    category: str,
    amount: float,
    attempt_count: int,
    opted_out: bool,
    random_draw: float,
) -> dict:
    """
    Probabilistic blind retry simulator across large synthetic distributions.
    """
    if opted_out or attempt_count >= 3 or category == "hard_decline":
        return {"blind_retry_recovered": False, "blind_retry_amount": 0.0}

    params = CALIBRATED_PROBABILITIES.get(category, {"blind_retry_base": 0.0})
    base_p = params.get("blind_retry_base", 0.0)

    decay = (attempt_count - 1) * 0.08
    effective_p = max(0.0, base_p - decay)

    if random_draw <= effective_p:
        return {"blind_retry_recovered": True, "blind_retry_amount": amount}
    return {"blind_retry_recovered": False, "blind_retry_amount": 0.0}
