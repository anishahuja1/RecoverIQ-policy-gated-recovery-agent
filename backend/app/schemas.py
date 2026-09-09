from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime

class DiagnosisOutput(BaseModel):
    diagnosis: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning_summary: str
    recommended_action: str
    customer_message_needed: bool
    risk_level: str

class PolicyOutput(BaseModel):
    decision: str  # approved | blocked | modified | escalated
    selected_action: str
    reason: str
    idempotency_key: Optional[str] = None
    blocked_rule: Optional[str] = None
    escalation_reason: Optional[str] = None

class AuditEntry(BaseModel):
    id: int
    payment_id: str
    batch_run_id: Optional[str]
    timestamp: datetime
    actor: str
    event_type: str
    message: str
    metadata: Optional[Any] = None
    prev_hash: Optional[str] = None
    event_hash: Optional[str] = None

    class Config:
        from_attributes = True

class PaymentOut(BaseModel):
    payment_id: str
    customer_id: str
    customer_name: str
    amount: float
    currency: str
    payment_method: str
    failure_category: str
    failure_code: str
    failure_message: str
    attempt_count: int
    customer_locale: str
    consent_for_voice: bool
    opted_out: bool
    created_at: datetime
    last_attempt_at: datetime
    status: str
    ai_diagnosis: Optional[str]
    ai_confidence: Optional[float]
    ai_reasoning: Optional[str]
    ai_recommended_action: Optional[str]
    ai_risk_level: Optional[str]
    policy_decision: Optional[str]
    policy_selected_action: Optional[str]
    policy_reason: Optional[str]
    policy_idempotency_key: Optional[str]
    policy_blocked_rule: Optional[str]
    policy_escalation_reason: Optional[str]
    action_taken: Optional[str]
    final_status: Optional[str]
    recovered_amount: float
    blind_retry_recovered: bool
    blind_retry_amount: float
    provenance: Optional[str] = "SEEDED_DEMO"

    class Config:
        from_attributes = True

class MetricsOut(BaseModel):
    total_payments: int
    total_at_risk: float
    ai_recovered_count: int
    ai_recovered_amount: float
    blind_retry_recovered_count: int
    blind_retry_recovered_amount: float
    ai_uplift_count: int
    ai_uplift_amount: float
    recovery_rate: float
    blind_retry_rate: float
    blocked_actions: int
    escalated_count: int
    unresolved_count: int
    needs_customer_action_count: int
    recovered_count: int
    not_recovered_count: int
    mode: str

class BatchRunOut(BaseModel):
    run_id: str
    mode: str
    payments: List[PaymentOut]
    metrics: MetricsOut
