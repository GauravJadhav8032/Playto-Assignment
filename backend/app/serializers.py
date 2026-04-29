"""DRF Serializers — input validation only. Output is built in services.py."""

import uuid
from rest_framework import serializers
from .models import Merchant, Payout


class PayoutCreateSerializer(serializers.Serializer):
    amount_paise = serializers.IntegerField(min_value=1)
    bank_account_id = serializers.CharField(max_length=255)

    def validate_amount_paise(self, value):
        if not isinstance(value, int):
            raise serializers.ValidationError("amount_paise must be an integer (paise).")
        return value


class MerchantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Merchant
        fields = ["id", "name"]
