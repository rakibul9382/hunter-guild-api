from .models import HunterEarning, Withdrawl
from django.db.models import Sum

def get_client_info(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', 'Unknown IP')
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    return {
        "ip_address": ip,
        "user_agent": user_agent,
    }


def get_available_balance(hunter):
    total_earned = HunterEarning.objects.filter(hunter=hunter).aggregate(total=Sum('amount'))['total'] or 0
    total_withdrawn = Withdrawl.objects.filter(hunter=hunter, status__in=['PENDING', 'APPROVED', 'COMPLETED', 'PROCESSING']).aggregate(total=Sum('amount'))['total'] or 0
    return total_earned-total_withdrawn
