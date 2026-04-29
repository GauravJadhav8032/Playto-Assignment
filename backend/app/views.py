"""
API Views — thin HTTP layer. All logic is in services.py.
"""

import uuid
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .serializers import PayoutCreateSerializer
from .services import (
    create_payout,
    get_dashboard_data,
    list_merchants,
    InsufficientFundsError,
    InvalidTransitionError,
)

logger = logging.getLogger("app")


class PayoutCreateView(APIView):
    """
    POST /api/v1/payouts

    Required header: Idempotency-Key: <UUID>
    Body: { "amount_paise": <int>, "bank_account_id": <str> }

    Returns the payout record (or cached response on duplicate key).
    """

    def post(self, request):
        # --- Parse & validate idempotency key header ---
        raw_key = request.headers.get("Idempotency-Key")
        if not raw_key:
            return Response(
                {"error": "Idempotency-Key header is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            idempotency_key = uuid.UUID(raw_key)
        except ValueError:
            return Response(
                {"error": "Idempotency-Key must be a valid UUID."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- merchant_id from query param (no auth in scope) ---
        merchant_id = request.query_params.get("merchant_id")
        if not merchant_id:
            return Response(
                {"error": "merchant_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            merchant_id = int(merchant_id)
        except ValueError:
            return Response({"error": "merchant_id must be an integer."}, status=400)

        # --- Validate body ---
        serializer = PayoutCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            response_data = create_payout(
                merchant_id=merchant_id,
                amount_paise=serializer.validated_data["amount_paise"],
                bank_account_id=serializer.validated_data["bank_account_id"],
                idempotency_key=idempotency_key,
            )
            return Response(response_data, status=status.HTTP_201_CREATED)

        except InsufficientFundsError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        except Exception as exc:
            logger.exception("Unexpected error in PayoutCreateView: %s", exc)
            return Response(
                {"error": "Internal server error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DashboardView(APIView):
    """
    GET /api/v1/dashboard?merchant_id=<id>

    Returns available_balance, held_balance, transactions, payouts.
    """

    def get(self, request):
        merchant_id = request.query_params.get("merchant_id")
        if not merchant_id:
            return Response(
                {"error": "merchant_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            merchant_id = int(merchant_id)
        except ValueError:
            return Response({"error": "merchant_id must be an integer."}, status=400)

        data = get_dashboard_data(merchant_id)
        return Response(data)


class MerchantListView(APIView):
    """
    GET /api/v1/merchants

    List all merchants — used by the frontend to populate the selector.
    """

    def get(self, request):
        return Response(list_merchants())
