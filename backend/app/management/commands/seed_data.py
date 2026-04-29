"""
Management command: seed_data

Creates sample merchants and ledger entries so the dashboard
shows meaningful data immediately after setup.

Usage:
    python manage.py seed_data
"""

from django.core.management.base import BaseCommand
from app.models import Merchant, LedgerEntry


class Command(BaseCommand):
    help = "Seed database with sample merchants and ledger entries."

    def handle(self, *args, **kwargs):
        merchants = [
            ("Acme Corp", 500_000),       # 5,000 INR
            ("Globex Inc", 1_000_000),     # 10,000 INR
            ("Initech Ltd", 250_000),      # 2,500 INR
        ]

        for name, credit in merchants:
            merchant, created = Merchant.objects.get_or_create(name=name)
            if created:
                LedgerEntry.objects.create(
                    merchant=merchant,
                    type=LedgerEntry.EntryType.CREDIT,
                    amount_paise=credit,
                    reference="initial_seed",
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created merchant '{name}' with {credit} paise credit."
                    )
                )
            else:
                self.stdout.write(f"Merchant '{name}' already exists — skipped.")

        self.stdout.write(self.style.SUCCESS("Seed complete."))
