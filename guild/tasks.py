import time
import uuid
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from .models import Withdrawl
from .services.razorpay_service import create_razorpay_payout
# The @shared_task decorator is what turns a normal Python function
# into a Celery background worker task.


@shared_task
def simulate_heavy_email_task(user_email):
    subject = "System alert: Hunter guild rank update"
    message = "Your registration and email evaluation were successful, This email is processed asynchronously by your new celery worker!"
    send_mail(
        subject=subject,
        message=message,
        from_email='skrakibulislam9623@gmail.com',
        recipient_list=[user_email],
        fail_silently=False
    )
    return f"Real email successfully sent to {user_email}!"

@shared_task
def send_otp_email_task(target_email, otp_code):
    """Sends the 6-digit OTP asynchronously during registration."""
    subject = 'Hunter Guild - Verify Your Email'
    message = f'Your verification code is: {otp_code}\n\nThis code will expire shortly. Do not share it with anyone.'

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[target_email],
        fail_silently=False,
    )
    return f"OTP sent to {target_email}"

@shared_task
def send_welcome_email_task(target_email, username):
    """Sends the official welcome email once account is activated."""
    subject = 'Welcome to the Hunter Guild!'
    message = f'Greetings {username},\n\nYour email has been verified and your account is now active. Welcome to the ranks!'

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[target_email],
        fail_silently=False,
    )
    return f"Welcome email sent to {target_email}"

@shared_task
def process_withdrawal_request_task(withdrawal_id):
    """Simulates processing a withdrawal request asynchronously."""
    try:
        withdrawal = Withdrawl.objects.get(id=withdrawal_id)
    except Withdrawl.DoesNotExist:
        return f"Withdrawal request with ID {withdrawal_id} does not exist."
    if withdrawal.status != 'APPROVED':
        return f"Withdrawal request with ID {withdrawal_id} is not approved for processing."
    fund_account_id = withdrawal.hunter.razorpay_fund_account_id

    if not fund_account_id:
        withdrawal.status = 'FAILED'
        withdrawal.admin_notes = "Hunter does not have a valid Razorpay fund account ID."
        withdrawal.save(update_fields=['status', 'admin_notes'])
        return f"Hunter does not have a valid Razorpay fund account ID for withdrawal request ID {withdrawal_id}."

    if not withdrawal.razorpay_idempotency_key:
        withdrawal.razorpay_idempotency_key = str(uuid.uuid4())
        withdrawal.save(update_fields=['razorpay_idempotency_key'])
    
    withdrawal.status = 'PROCESSING'
    withdrawal.save(update_fields=['status'])
    try:
        payout_response = create_razorpay_payout(
            fund_account_id=fund_account_id,
            amount=withdrawal.amount,
            reference_id=str(withdrawal.id),
            idempotency_key=withdrawal.razorpay_idempotency_key
        )
        withdrawal.razorpay_payout_id = payout_response.get('id')
        withdrawal.save(update_fields=['razorpay_payout_id'])
    except Exception as e:
        withdrawal.status = 'FAILED'
        withdrawal.admin_notes = f"Razorpay payout failed: {str(e)}"
        withdrawal.save(update_fields=['status', 'admin_notes'])
        return f"Razorpay payout failed for withdrawal request ID {withdrawal_id}: {str(e)}"

@shared_task
def process_razorpay_webhook_task(event_id, event, payload):
    """Processes Razorpay webhook events asynchronously."""
    payout_id = payload.get('payload', {}).get('payout', {}).get('entity', {}).get('id')
    if not payout_id:
        return f"Webhook event {event_id} does not contain a valid payout ID."
    try:
        withdrawal = Withdrawl.objects.get(razorpay_payout_id=payout_id)
    except Withdrawl.DoesNotExist:
        return f"No withdrawal request found for Razorpay payout ID {payout_id} in webhook event {event_id}."

    if event == 'payout.processed':
        withdrawal.status = 'COMPLETED'
        withdrawal.admin_notes = "Payout processed successfully via Razorpay."
    elif event == 'payout.failed':
        withdrawal.status = 'FAILED'
        failure_reason = payload.get('payload', {}).get('payout', {}).get('entity', {}).get('failure_reason', 'Unknown reason')
        withdrawal.admin_notes = f"Payout failed via Razorpay. Reason: {failure_reason}"
    else:
        return f"Webhook event {event_id} with event type {event} is not handled."

    withdrawal.save(update_fields=['status', 'admin_notes'])

