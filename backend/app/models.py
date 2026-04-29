"""
Data models for the Payout Engine.

Design decisions:
- amount_paise uses BigIntegerField — all money stored as integer paise, no floats.
- LedgerEntry is append-only; balance is never stored, always computed.
- IdempotencyKey has a DB-level UNIQUE constraint on (merchant, key).
"""

import uuid
from django.db import models


class Merchant(models.Model):
    name = models.CharField(max_length=255)

    class Meta:
        db_table = "merchants"

    def __str__(self):
        return f"{self.name} (id={self.id})"


class LedgerEntry(models.Model):
    class EntryType(models.TextChoices):
        CREDIT = "CREDIT", "Credit"
        DEBIT = "DEBIT", "Debit"

    merchant = models.ForeignKey(
        Merchant, on_delete=models.PROTECT, related_name="ledger_entries"
    )
    type = models.CharField(max_length=10, choices=EntryType.choices)
    # Store money as integer paise only — no decimals, no floats.
    amount_paise = models.BigIntegerField()
    reference = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ledger_entries"
        indexes = [
            models.Index(fields=["merchant"], name="idx_ledger_merchant"),
        ]

    def __str__(self):
        return f"{self.type} {self.amount_paise}p for merchant {self.merchant_id}"


class Payout(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    # Valid state transitions enforced in services.py
    VALID_TRANSITIONS: dict[str, list[str]] = {
        "pending": ["processing"],
        "processing": ["completed", "failed"],
    }

    merchant = models.ForeignKey(
        Merchant, on_delete=models.PROTECT, related_name="payouts"
    )
    amount_paise = models.BigIntegerField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    # UUID stored on payout for fast lookup; IdempotencyKey table is the source of truth.
    idempotency_key = models.UUIDField(default=uuid.uuid4)
    attempts = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payouts"
        indexes = [
            models.Index(fields=["status"], name="idx_payout_status"),
            models.Index(fields=["merchant"], name="idx_payout_merchant"),
        ]

    def __str__(self):
        return f"Payout {self.id} [{self.status}] {self.amount_paise}p"


class IdempotencyKey(models.Model):
    merchant = models.ForeignKey(
        Merchant, on_delete=models.PROTECT, related_name="idempotency_keys"
    )
    # UUID key supplied by client in Idempotency-Key header.
    key = models.UUIDField()
    # Full JSON response stored so repeat requests get identical replies.
    response = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "idempotency_keys"
        # DB-level guarantee: one key per merchant — prevents duplicates even
        # under concurrent requests where two transactions race to insert.
        constraints = [
            models.UniqueConstraint(
                fields=["merchant", "key"], name="idx_idem_key"
            )
        ]

    def __str__(self):
        return f"IdempotencyKey {self.key} merchant={self.merchant_id}"
