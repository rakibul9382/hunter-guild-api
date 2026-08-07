from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from guild.models import SecurityLog


class Command(BaseCommand):
    help = "Permanently deletes security logs that are older than 7 days."

    def handel(self, *args, **options):
        cutoff_date = timezone.now() - timedelta(days=7)
        old_logs = SecurityLog.objects.filter(timestamp__lt=cutoff_date)
        count = old_logs.count()
        if count > 0:
            old_logs.delete()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Cleaned up {count} outdated log entries."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Database is clean. No outdated logs found."
                )
            )
