import requests

from django.conf import settings

def create_razorpay_payout(fund_account_id, amount, reference_id, idempotency_key):
    url = "https://api.razorpay.com/v1/payouts"
    headers = {
        "Content-Type": "application/json",
        'X-Payout-idempotency': idempotency_key,  # Unique ID for idempotency
    }
    payload = {
        "account_number": settings.RAZORPAYX_ACCOUNT_NUMBER,
        "fund_account_id": fund_account_id,
        "amount": amount * 100,  # Amount in paise
        "currency": "INR",
        "mode": "UPI",
        "purpose": "payout",
        "queue_if_low_balance": True,
        "reference_id": reference_id,
        "narration": f"Payout for withdrawal request {reference_id}",
    }
    response = requests.post(url, json=payload, headers=headers, auth=(settings.RAZORPAYX_KEY_ID, settings.RAZORPAYX_KEY_SECRET),timeout=15)
    response.raise_for_status()  # Raise an error for bad responses
    return response.json()