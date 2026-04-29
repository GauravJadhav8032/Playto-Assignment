"""Django admin registration."""

from django.contrib import admin
from .models import Merchant, LedgerEntry, Payout, IdempotencyKey


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ["id", "name"]


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ["id", "merchant", "type", "amount_paise", "reference", "created_at"]
    list_filter = ["type", "merchant"]
    ordering = ["-created_at"]


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ["id", "merchant", "amount_paise", "status", "attempts", "created_at", "updated_at"]
    list_filter = ["status", "merchant"]
    ordering = ["-created_at"]


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ["id", "merchant", "key", "created_at"]
    ordering = ["-created_at"]
