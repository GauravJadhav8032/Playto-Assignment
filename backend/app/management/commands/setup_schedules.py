"""
Management command: setup_schedules

Registers the retry_stuck_payouts scheduled task in Django-Q so that
stuck payouts are automatically retried every 60 seconds.

Usage:
    python manage.py setup_schedules
"""

from django.core.management.base import BaseCommand
from django_q.models import Schedule


class Command(BaseCommand):
    help = "Register Django-Q scheduled tasks (idempotent — safe to run multiple times)."

    def handle(self, *args, **kwargs):
        # Register retry checker — runs every 60 seconds
        schedule, created = Schedule.objects.update_or_create(
            name="Retry Stuck Payouts",
            defaults={
                "func": "app.tasks.run_retry_stuck_payouts",
                "schedule_type": Schedule.MINUTES,
                "minutes": 1,
                "repeats": -1,   # repeat forever
            },
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    "Created schedule: 'Retry Stuck Payouts' — runs every 60 seconds."
                )
            )
        else:
            self.stdout.write("Schedule 'Retry Stuck Payouts' already exists — updated.")
