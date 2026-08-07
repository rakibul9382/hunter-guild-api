from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from .models import SecurityLog

def get_client_data(request):
    if not request:
        return "Unknown IP", "Unknown Device"
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', 'Unknown IP')
        
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown Device')
    return ip, user_agent

@receiver(user_logged_in)
def log_successful_login(sender, request, user, **kwargs):
    ip, ua = get_client_data(request)
    SecurityLog.objects.create(
        user=user,
        username_attempted=user.username,
        action='LOGIN_SUCCESS',
        ip_address=ip,
        user_agent=ua
    )

@receiver(user_login_failed)
def log_login_failed(sender, request, credentials, **kwargs):
    ip, ua = get_client_data(request)
    attempted_username = credentials.get('username', 'Unknown Input')
    
    SecurityLog.objects.create(
        user=None,  # No matching user because the password/credential combination was wrong
        username_attempted=attempted_username,
        action='LOGIN_FAILED',
        ip_address=ip,
        user_agent=ua
    )

@receiver(user_logged_out)
def log_user_logout(sender, user, request, **kwargs):
    if user:
        ip, ua = get_client_data(request)
        SecurityLog.objects.create(
            user=user,
            username_attempted=user.username,
            action='LOGOUT',
            ip_address=ip,
            user_agent=ua
        )
