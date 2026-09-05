"""
Metrics aggregator.

Computes all dashboard KPIs from the payments table after a batch run.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from .models import Payment
from .schemas import MetricsOut
from .config import settings


def compute_metrics(db: Session, mode: str) -> MetricsOut:
    payments = db.query(Payment).all()

    total_payments = len(payments)
    total_at_risk = sum(p.amount for p in payments)

    # AI recovery
    ai_recovered = [p for p in payments if p.final_status == "recovered"]
    ai_recovered_count = len(ai_recovered)
    ai_recovered_amount = sum(p.recovered_amount for p in ai_recovered)

    # Blind retry baseline
    blind_recovered = [p for p in payments if p.blind_retry_recovered]
    blind_retry_count = len(blind_recovered)
    blind_retry_amount = sum(p.blind_retry_amount for p in blind_recovered)

    # Uplift (AI minus blind retry)
    ai_uplift_count = ai_recovered_count - blind_retry_count
    ai_uplift_amount = ai_recovered_amount - blind_retry_amount

    # Rates
    recovery_rate = round(ai_recovered_count / total_payments * 100, 1) if total_payments else 0
    blind_retry_rate = round(blind_retry_count / total_payments * 100, 1) if total_payments else 0

    # Status counts
    blocked = sum(1 for p in payments if p.final_status == "blocked")
    escalated = sum(1 for p in payments if p.final_status == "escalated")
    unresolved = sum(1 for p in payments if p.final_status == "unresolved")
    needs_customer = sum(1 for p in payments if p.final_status == "needs_customer_action")
    not_recovered = sum(1 for p in payments if p.final_status == "not_recovered")

    return MetricsOut(
        total_payments=total_payments,
        total_at_risk=round(total_at_risk, 2),
        ai_recovered_count=ai_recovered_count,
        ai_recovered_amount=round(ai_recovered_amount, 2),
        blind_retry_recovered_count=blind_retry_count,
        blind_retry_recovered_amount=round(blind_retry_amount, 2),
        ai_uplift_count=ai_uplift_count,
        ai_uplift_amount=round(ai_uplift_amount, 2),
        recovery_rate=recovery_rate,
        blind_retry_rate=blind_retry_rate,
        blocked_actions=blocked,
        escalated_count=escalated,
        unresolved_count=unresolved,
        needs_customer_action_count=needs_customer,
        recovered_count=ai_recovered_count,
        not_recovered_count=not_recovered,
        mode=mode,
    )
