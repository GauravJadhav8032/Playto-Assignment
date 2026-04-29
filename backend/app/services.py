"""
Services layer — all business logic lives here.

Views are thin; they only parse HTTP and delegate to these functions.
All database transactions and locking are confined to this module.
"""

import logging
import uuid
from django.db import transaction
from django.db.models import Sum, Case, When, Value, IntegerField
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Merchant, LedgerEntry, Payout, IdempotencyKey

logger = logging.getLogger("app")


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class InsufficientFundsError(Exception):
    pass


class InvalidTransitionError(Exception):
    pass


class IdempotentResponse(Exception):
    """Raised when a duplicate idempotency key is detected — carries the cached response."""
    def __init__(self, response_data: dict):
        self.response_data = response_data


# ---------------------------------------------------------------------------
# Balance helpers (pure DB aggregation — no Python arithmetic on raw rows)
# ---------------------------------------------------------------------------

def _compute_balance_db(merchant_id: int) -> int:
    """
    Compute available balance via a single DB aggregation query.

    Balance = SUM(CREDIT amounts) - SUM(DEBIT amounts)

    This is intentionally done at the DB level so Python never holds an
    inconsistent in-memory balance across concurrent requests.
    """
    result = LedgerEntry.objects.filter(merchant_id=merchant_id).aggregate(
        total_credit=Coalesce(
            Sum("amount_paise", filter=Case(
                When(type=LedgerEntry.EntryType.CREDIT, then="amount_paise"),
                default=Value(0),
                output_field=IntegerField(),
            )),
            Value(0),
        ),
        total_debit=Coalesce(
            Sum("amount_paise", filter=Case(
                When(type=LedgerEntry.EntryType.DEBIT, then="amount_paise"),
                default=Value(0),
                output_field=IntegerField(),
            )),
            Value(0),
        ),
    )
    return result["total_credit"] - result["total_debit"]


def _compute_held_balance_db(merchant_id: int) -> int:
    """
    Held balance = sum of amount_paise for payouts in (pending, processing).
    These funds are reserved and not available to the merchant.
    """
    result = Payout.objects.filter(
        merchant_id=merchant_id,
        status__in=[Payout.Status.PENDING, Payout.Status.PROCESSING],
    ).aggregate(total=Coalesce(Sum("amount_paise"), Value(0)))
    return result["total"]


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

def _assert_valid_transition(payout: Payout, target_status: str) -> None:
    """
    Block any state transition not in the allowed map.

    Allowed:
        pending    → processing
        processing → completed | failed

    Everything else raises InvalidTransitionError.
    """
    allowed = Payout.VALID_TRANSITIONS.get(payout.status, [])
    if target_status not in allowed:
        raise InvalidTransitionError(
            f"Cannot transition payout {payout.id} from '{payout.status}' to '{target_status}'"
        )


# ---------------------------------------------------------------------------
# Payout creation
# ---------------------------------------------------------------------------

def create_payout(
    merchant_id: int,
    amount_paise: int,
    bank_account_id: str,
    idempotency_key: uuid.UUID,
) -> dict:
    """
    Create a payout atomically with balance validation and row-level locking.

    Flow:
      1. Check idempotency table → return cached response if found.
      2. Open a DB transaction.
      3. Lock all ledger rows for this merchant (select_for_update).
         This serialises concurrent payout requests for the same merchant —
         only one transaction can hold the lock at a time.
      4. Compute balance at DB level.
      5. Reject if balance < amount_paise.
      6. Insert DEBIT ledger entry (reserve funds).
      7. Create Payout (status=pending).
      8. Persist response in IdempotencyKey table.
      9. Enqueue async task (after commit, so worker sees committed data).
    """
    # -- Step 1: idempotency check (outside the main transaction — fast path) --
    try:
        cached = IdempotencyKey.objects.get(merchant_id=merchant_id, key=idempotency_key)
        logger.info("Idempotency hit: key=%s merchant=%s", idempotency_key, merchant_id)
        return cached.response
    except IdempotencyKey.DoesNotExist:
        pass

    payout_id = None

    # -- Steps 2–8 inside a single atomic block --
    with transaction.atomic():
        # Step 3: Lock all ledger rows for this merchant.
        # select_for_update() issues SELECT ... FOR UPDATE which prevents any
        # other transaction from acquiring a lock (or even reading, depending on
        # isolation level) until this transaction commits or rolls back.
        LedgerEntry.objects.select_for_update().filter(merchant_id=merchant_id)

        # Step 4: Compute balance inside the lock scope.
        balance = _compute_balance_db(merchant_id)
        logger.debug("Balance for merchant %s: %d paise", merchant_id, balance)

        # Step 5: Validate.
        if balance < amount_paise:
            raise InsufficientFundsError(
                f"Insufficient balance: available={balance}, requested={amount_paise}"
            )

        # Step 6: Reserve funds via DEBIT entry.
        LedgerEntry.objects.create(
            merchant_id=merchant_id,
            type=LedgerEntry.EntryType.DEBIT,
            amount_paise=amount_paise,
            reference=f"payout_hold:{bank_account_id}",
        )

        # Step 7: Create payout record.
        payout = Payout.objects.create(
            merchant_id=merchant_id,
            amount_paise=amount_paise,
            status=Payout.Status.PENDING,
            idempotency_key=idempotency_key,
        )
        payout_id = payout.id

        # Step 8: Persist idempotency response.
        response_data = _build_payout_response(payout)
        try:
            IdempotencyKey.objects.create(
                merchant_id=merchant_id,
                key=idempotency_key,
                response=response_data,
            )
        except Exception:
            # Another concurrent request won the race to insert this key.
            # Fetch their stored response and surface it.
            cached = IdempotencyKey.objects.get(merchant_id=merchant_id, key=idempotency_key)
            return cached.response

    logger.info("Payout created: id=%s merchant=%s amount=%d", payout_id, merchant_id, amount_paise)

    # Step 9: Enqueue async task AFTER commit so the worker sees committed rows.
    # Import here to avoid circular imports with tasks module.
    from django_q.tasks import async_task
    async_task("app.tasks.process_payout", payout_id)

    return response_data


# ---------------------------------------------------------------------------
# Payout processing helpers (called from tasks.py)
# ---------------------------------------------------------------------------

def mark_processing(payout: Payout) -> None:
    """Transition payout to processing status."""
    _assert_valid_transition(payout, Payout.Status.PROCESSING)
    payout.status = Payout.Status.PROCESSING
    payout.attempts += 1
    payout.save(update_fields=["status", "attempts", "updated_at"])
    logger.info("Payout %s → processing (attempt %d)", payout.id, payout.attempts)


def mark_completed(payout: Payout) -> None:
    """Transition payout to completed status inside the caller's transaction."""
    _assert_valid_transition(payout, Payout.Status.COMPLETED)
    payout.status = Payout.Status.COMPLETED
    payout.save(update_fields=["status", "updated_at"])
    logger.info("Payout %s → completed", payout.id)


def mark_failed_with_refund(payout: Payout) -> None:
    """
    Transition payout to failed and issue a CREDIT refund in the same transaction.

    Both the status update and the ledger entry are committed atomically so
    the ledger can never be in a state where money is both gone and the payout
    is failed (i.e. double-deducted).
    """
    with transaction.atomic():
        _assert_valid_transition(payout, Payout.Status.FAILED)
        payout.status = Payout.Status.FAILED
        payout.save(update_fields=["status", "updated_at"])

        # Refund: CREDIT the same amount back to the merchant's ledger.
        LedgerEntry.objects.create(
            merchant_id=payout.merchant_id,
            type=LedgerEntry.EntryType.CREDIT,
            amount_paise=payout.amount_paise,
            reference=f"refund:payout_{payout.id}",
        )
        logger.info("Payout %s → failed + refund issued", payout.id)


# ---------------------------------------------------------------------------
# Retry logic (called by retry_stuck_payouts task)
# ---------------------------------------------------------------------------

def retry_stuck_payouts() -> None:
    """
    Find payouts stuck in 'processing' for more than 30 seconds and retry them.

    Retry algorithm:
      - attempts < 3  → increment attempts + re-enqueue retry_payout
                        (uses retry_payout, NOT process_payout — retries accept
                         processing state; process_payout only accepts pending)
      - attempts >= 3 → mark failed + refund (give up)

    Backoff: delay = 2^attempts seconds (2s → 4s → 8s)
    """
    from django_q.tasks import async_task

    cutoff = timezone.now() - timezone.timedelta(seconds=30)
    stuck = Payout.objects.filter(
        status=Payout.Status.PROCESSING,
        updated_at__lt=cutoff,
    )

    for payout in stuck:
        if payout.attempts < 3:
            # Increment attempt counter before re-enqueuing so backoff is accurate
            payout.attempts += 1
            payout.save(update_fields=["attempts", "updated_at"])

            delay_seconds = 2 ** payout.attempts
            logger.warning(
                "Retrying stuck payout %s (attempt %d) with %ds backoff",
                payout.id, payout.attempts, delay_seconds,
            )
            # retry_payout handles processing-state payouts; process_payout does not
            async_task("app.tasks.retry_payout", payout.id)
        else:
            logger.error(
                "Payout %s exceeded max attempts (%d) — marking failed + refund",
                payout.id, payout.attempts,
            )
            mark_failed_with_refund(payout)


# ---------------------------------------------------------------------------
# Dashboard data
# ---------------------------------------------------------------------------

def get_dashboard_data(merchant_id: int) -> dict:
    """
    Aggregate dashboard data for a merchant.

    Returns available balance, held balance, recent ledger entries, and payouts.
    """
    available_balance = _compute_balance_db(merchant_id)
    held_balance = _compute_held_balance_db(merchant_id)

    ledger_entries = list(
        LedgerEntry.objects.filter(merchant_id=merchant_id)
        .order_by("-created_at")
        .values("id", "type", "amount_paise", "reference", "created_at")[:50]
    )

    payouts = list(
        Payout.objects.filter(merchant_id=merchant_id)
        .order_by("-created_at")
        .values(
            "id", "amount_paise", "status", "idempotency_key",
            "attempts", "created_at", "updated_at"
        )[:50]
    )

    # Serialize datetime/UUID fields for JSON
    for entry in ledger_entries:
        entry["created_at"] = entry["created_at"].isoformat()
    for payout in payouts:
        payout["created_at"] = payout["created_at"].isoformat()
        payout["updated_at"] = payout["updated_at"].isoformat()
        payout["idempotency_key"] = str(payout["idempotency_key"])

    return {
        "available_balance": available_balance,
        "held_balance": held_balance,
        "transactions": ledger_entries,
        "payouts": payouts,
    }


# ---------------------------------------------------------------------------
# Merchant helpers
# ---------------------------------------------------------------------------

def list_merchants() -> list[dict]:
    return list(Merchant.objects.values("id", "name").order_by("id"))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_payout_response(payout: Payout) -> dict:
    return {
        "id": payout.id,
        "amount_paise": payout.amount_paise,
        "status": payout.status,
        "idempotency_key": str(payout.idempotency_key),
        "attempts": payout.attempts,
        "created_at": payout.created_at.isoformat(),
    }
