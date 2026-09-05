from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from .database import Base

class Payment(Base):
    __tablename__ = "payments"

    payment_id = Column(String, primary_key=True, index=True)
    customer_id = Column(String, nullable=False)
    customer_name = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    payment_method = Column(String, nullable=False)
    failure_category = Column(String, nullable=False)
    failure_code = Column(String, nullable=False)
    failure_message = Column(String, nullable=False)
    attempt_count = Column(Integer, default=1)
    customer_locale = Column(String, default="en-IN")
    consent_for_voice = Column(Boolean, default=False)
    opted_out = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False)
    last_attempt_at = Column(DateTime, nullable=False)
    hidden_recovery_outcome = Column(String, nullable=False)

    # Fields set after batch run
    status = Column(String, default="pending")
    ai_diagnosis = Column(String, nullable=True)
    ai_confidence = Column(Float, nullable=True)
    ai_reasoning = Column(Text, nullable=True)
    ai_recommended_action = Column(String, nullable=True)
    ai_risk_level = Column(String, nullable=True)
    policy_decision = Column(String, nullable=True)
    policy_selected_action = Column(String, nullable=True)
    policy_reason = Column(String, nullable=True)
    policy_idempotency_key = Column(String, nullable=True)
    policy_blocked_rule = Column(String, nullable=True)
    policy_escalation_reason = Column(String, nullable=True)
    action_taken = Column(String, nullable=True)
    final_status = Column(String, nullable=True)
    recovered_amount = Column(Float, default=0.0)
    batch_run_id = Column(String, nullable=True)

    # Blind retry baseline
    blind_retry_recovered = Column(Boolean, default=False)
    blind_retry_amount = Column(Float, default=0.0)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_id = Column(String, index=True, nullable=False)
    batch_run_id = Column(String, nullable=True)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    actor = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, nullable=True)


class BatchRun(Base):
    __tablename__ = "batch_runs"

    run_id = Column(String, primary_key=True)
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    mode = Column(String, default="DEMO_MODE")
    total_payments = Column(Integer, default=0)
    recovered_count = Column(Integer, default=0)
    blocked_count = Column(Integer, default=0)
    escalated_count = Column(Integer, default=0)
