from django.contrib import admin
from .models import User, HunterProfile, Task, TaskAssignment, Payment, AuditLog,OTPRecord, Notification
# Register your models here.
admin.site.register(User)
admin.site.register(HunterProfile)
admin.site.register(Task)
admin.site.register(TaskAssignment)
admin.site.register(Payment)
admin.site.register(AuditLog)
admin.site.register(OTPRecord)
admin.site.register(Notification)