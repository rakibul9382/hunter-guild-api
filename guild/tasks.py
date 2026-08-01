import time
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
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
