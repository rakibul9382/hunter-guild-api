import hashlib
import hmac
import json
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .tasks import process_razorpay_webhook_task

@csrf_exempt
def razorpay_webhook(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'only post requests allowed'}, status=405)
    body = request.body
    signature = request.headers.get('X-Razorpay-Signature')
    if not signature:
        return JsonResponse({'error': 'signature missing'}, status=400)
    webhook_secret = settings.webhook_secret
    expected_signature = hmac.new(
        key=webhook_secret.encode(),
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        return JsonResponse({'error': 'invalid signature'}, status=400)
    payload = json.loads(body)
    event_id = request.headers.get('X-Razorpay-Event-Id')
    event = payload.get('event')
    if event not in ['payout.processed', 'payout.failed']:
        return JsonResponse({'error': 'event not handled'}, status=400)
    process_razorpay_webhook_task.delay(event_id, event, payload)
    return HttpResponse(status=200)
