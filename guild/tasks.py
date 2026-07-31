import time
from celery import shared_task

# The @shared_task decorator is what turns a normal Python function
# into a Celery background worker task.


@shared_task
def simulate_heavy_email_task(user_email):
    print(f"CELERY WORKER: Starting to send email to {user_email}...")

    # Freeze this specific background process for 10 seconds
    time.sleep(10) 

    print(f"CELERY WORKER: Successfully sent email to {user_email}!")
    return "Done"
