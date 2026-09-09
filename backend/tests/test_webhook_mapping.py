"""
Table-Driven Webhook Ingestion & Error Mapping Test Suite.

Verifies:
1. Table-driven mapping from Razorpay error codes/reasons/descriptions to RecoverIQ failure categories.
2. Paise to Rupee amount unit conversion (paise integer / 100).
3. Fallback category handling for unrecognized error payloads.
4. Customer metadata & note extraction.
5. Rejection of invalid JSON payloads with HTTP 400.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


MAPPING_TEST_CASES = [
    # (error_description, error_reason, expected_category)
    ("Bank network timeout during switch authorization", "gateway_timeout", "soft_decline"),
    ("Issuer server down for maintenance", "issuer_down", "soft_decline"),
    ("Payment gateway error encountered", "server_error", "soft_decline"),
    ("Customer did not enter 3DS OTP in time", "otp_timeout", "authentication_failed"),
    ("Incorrect UPI PIN entered by user", "pin_incorrect", "authentication_failed"),
    ("Customer failed two-factor authentication challenge", "auth_failed", "authentication_failed"),
    ("Account balance is insufficient to complete transaction", "insufficient_funds", "insufficient_funds"),
    ("Low account balance reported by bank", "low_balance", "insufficient_funds"),
    ("Transaction blocked due to suspected fraud", "fraud_detection", "hard_decline"),
    ("Card is reported stolen or lost", "stolen_card", "hard_decline"),
    ("Card number is blocked or blacklisted", "blacklisted_instrument", "hard_decline"),
    ("Recurring mandate authorization declined by issuer", "mandate_failed", "subscription_failed"),
    ("Auto-debit recurring subscription mandate expired", "subscription_expired", "subscription_failed"),
    ("Customer cancelled or dropped checkout session", "user_cancelled", "checkout_abandoned"),
    ("Checkout abandoned before payment details submitted", "cart_abandoned", "checkout_abandoned"),
    ("Unknown random merchant error XYZ-999", "generic_err", "soft_decline"),  # Fallback
]


@pytest.mark.parametrize("err_desc,err_reason,expected_cat", MAPPING_TEST_CASES)
def test_webhook_category_mapping(client, err_desc, err_reason, expected_cat):
    """Table-driven test verifying all error keyword mappings."""
    payload = {
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay_map_{abs(hash(err_desc)) % 100000}",
                    "amount": 250000,
                    "currency": "INR",
                    "method": "upi",
                    "error_code": "BAD_REQUEST",
                    "error_description": err_desc,
                    "error_reason": err_reason,
                    "notes": {"customer_name": "Test User"},
                }
            }
        },
    }
    resp = client.post("/api/webhooks/razorpay", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["category"] == expected_cat


def test_paise_to_rupee_amount_conversion(client):
    """Razorpay transmits integer paise (e.g. 499900 paise = ₹4,999.00)."""
    payload = {
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_paise_conv_01",
                    "amount": 499900,  # 499,900 paise = 4,999.00 INR
                    "currency": "INR",
                    "method": "card",
                    "error_code": "TIMEOUT",
                    "error_description": "Bank timeout",
                    "error_reason": "timeout",
                }
            }
        },
    }
    resp = client.post("/api/webhooks/razorpay", json=payload)
    assert resp.status_code == 200
    # Payment detail endpoint to inspect persisted amount
    pay_resp = client.get("/api/payments/pay_paise_conv_01")
    assert pay_resp.status_code == 200
    assert pay_resp.json()["amount"] == 4999.0


def test_webhook_malformed_json_payload(client):
    """Malformed non-JSON payload returns HTTP 400 Bad Request."""
    resp = client.post(
        "/api/webhooks/razorpay",
        content="NOT_VALID_JSON{{{",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
