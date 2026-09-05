"""
Diagnosis Engine — DEMO_MODE (default) + optional LIVE_AI_MODE.

DEMO_MODE: Returns cached, deterministic structured outputs per failure_category.
           No external API calls. Same schema as live mode.
LIVE_AI_MODE: Activated only when GEMINI_API_KEY or OPENAI_API_KEY is present.
              Falls back to DEMO_MODE if API call fails.

The LLM (in live mode) only PROPOSES a diagnosis — it never executes actions.
"""
from .schemas import DiagnosisOutput
from .config import settings

# ── Cached deterministic diagnosis per failure category ───────────────────────
CACHED_DIAGNOSES: dict[str, dict] = {
    "soft_decline": {
        "diagnosis": "soft_decline",
        "confidence": 0.86,
        "reasoning_summary": (
            "Issuer timeout or transient bank error detected. "
            "Pattern is consistent with retryable transient failures. "
            "No fraud indicators present. Retry after a delay is appropriate."
        ),
        "recommended_action": "retry_later",
        "customer_message_needed": False,
        "risk_level": "low",
    },
    "insufficient_funds": {
        "diagnosis": "insufficient_funds",
        "confidence": 0.91,
        "reasoning_summary": (
            "Balance insufficient at time of transaction. "
            "Customer may top up account or use alternate payment method. "
            "A payment link reminder is the most effective recovery action."
        ),
        "recommended_action": "payment_link_reminder",
        "customer_message_needed": True,
        "risk_level": "medium",
    },
    "hard_decline": {
        "diagnosis": "hard_decline",
        "confidence": 0.97,
        "reasoning_summary": (
            "Card is blocked, invalid, or flagged for suspected fraud by the issuer. "
            "This is a permanent, non-retryable failure. "
            "No recovery action is possible without customer replacing the card."
        ),
        "recommended_action": "stop_no_retry",
        "customer_message_needed": False,
        "risk_level": "high",
    },
    "authentication_failed": {
        "diagnosis": "authentication_failed",
        "confidence": 0.82,
        "reasoning_summary": (
            "3DS challenge, OTP, or UPI PIN authentication was not completed successfully. "
            "Customer needs to retry authentication. "
            "A targeted reminder with a fresh payment link should resolve this."
        ),
        "recommended_action": "customer_action_reminder",
        "customer_message_needed": True,
        "risk_level": "medium",
    },
    "checkout_abandoned": {
        "diagnosis": "checkout_abandoned",
        "confidence": 0.78,
        "reasoning_summary": (
            "Customer initiated but did not complete the checkout flow. "
            "Dropout could be due to distraction or payment friction. "
            "A personalized reminder message with checkout link may recover this."
        ),
        "recommended_action": "reminder_message",
        "customer_message_needed": True,
        "risk_level": "low",
    },
    "subscription_failed": {
        "diagnosis": "subscription_failed",
        "confidence": 0.88,
        "reasoning_summary": (
            "Auto-debit mandate or recurring charge failed. "
            "Bank may have declined the recurring authorization. "
            "Retry with a simultaneous reminder to the customer is recommended."
        ),
        "recommended_action": "retry_plus_reminder",
        "customer_message_needed": True,
        "risk_level": "medium",
    },
}

# Low-confidence variant: used for ambiguous payments (e.g. pay_SD009)
LOW_CONFIDENCE_OVERRIDE: set[str] = {"pay_SD009"}
LOW_CONFIDENCE_DIAGNOSIS = {
    "soft_decline": {
        "diagnosis": "soft_decline",
        "confidence": 0.48,
        "reasoning_summary": (
            "Failure pattern is ambiguous. Could be transient or a soft hard-decline. "
            "Confidence is below threshold — escalating for manual review."
        ),
        "recommended_action": "retry_later",
        "customer_message_needed": False,
        "risk_level": "medium",
    }
}


def run_demo_diagnosis(payment_id: str, failure_category: str) -> DiagnosisOutput:
    """Return cached deterministic diagnosis for a given failure category."""
    if payment_id in LOW_CONFIDENCE_OVERRIDE:
        raw = LOW_CONFIDENCE_DIAGNOSIS.get(failure_category, CACHED_DIAGNOSES[failure_category])
    else:
        raw = CACHED_DIAGNOSES.get(failure_category)
        if raw is None:
            raise ValueError(f"Unknown failure_category: {failure_category}")
    return DiagnosisOutput(**raw)


async def run_live_diagnosis(payment: dict) -> DiagnosisOutput:
    """
    Live AI diagnosis via Gemini or OpenAI (structured JSON output).
    Falls back to DEMO_MODE on any error.
    """
    try:
        if settings.gemini_api_key:
            return await _gemini_diagnosis(payment)
        elif settings.openai_api_key:
            return await _openai_diagnosis(payment)
    except Exception:
        pass
    # Graceful fallback
    return run_demo_diagnosis(payment["payment_id"], payment["failure_category"])


async def _gemini_diagnosis(payment: dict) -> DiagnosisOutput:
    import httpx, json
    prompt = _build_prompt(payment)
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-1.5-flash:generateContent"
        f"?key={settings.gemini_api_key}"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return DiagnosisOutput(**json.loads(text))


async def _openai_diagnosis(payment: dict) -> DiagnosisOutput:
    import httpx, json
    prompt = _build_prompt(payment)
    body = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            json=body,
            headers=headers,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        return DiagnosisOutput(**json.loads(text))


def _build_prompt(payment: dict) -> str:
    return f"""You are a payment failure diagnosis engine for an Indian fintech platform.
Analyze the following failed payment and return a JSON diagnosis.

Payment data:
- failure_category: {payment.get("failure_category")}
- failure_code: {payment.get("failure_code")}
- failure_message: {payment.get("failure_message")}
- amount: ₹{payment.get("amount")}
- payment_method: {payment.get("payment_method")}
- attempt_count: {payment.get("attempt_count")}

Return ONLY a valid JSON object with these exact fields:
{{
  "diagnosis": "<failure category string>",
  "confidence": <float 0.0-1.0>,
  "reasoning_summary": "<1-2 sentence explanation>",
  "recommended_action": "<one of: retry_later|payment_link_reminder|stop_no_retry|customer_action_reminder|reminder_message|retry_plus_reminder>",
  "customer_message_needed": <true|false>,
  "risk_level": "<low|medium|high>"
}}"""


async def diagnose(payment_id: str, failure_category: str, payment_dict: dict) -> DiagnosisOutput:
    """Main entry point. Uses DEMO_MODE by default, LIVE_AI_MODE if API key configured."""
    if settings.demo_mode:
        return run_demo_diagnosis(payment_id, failure_category)
    else:
        return await run_live_diagnosis(payment_dict)
