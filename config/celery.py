import os
from celery import Celery

# Point to config.settings instead of hunter_project.settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Name the app 'config'
app = Celery('config')

app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()