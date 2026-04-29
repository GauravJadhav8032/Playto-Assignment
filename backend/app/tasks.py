"""
Async tasks executed by the Django-Q worker process.

These run in a separate process (python manage.py qcluster) and must
be fully self-contained — they re-fetch DB state to avoid stale data.
"""

import random
import logging

from django.db import transaction

from .models import Payout
from .services import mark_processing, mark_completed, mark_failed_with_refund

logger = logging.getLogger("app")


def _simulate_and_settle(payout: Payout) -> None:
    """
    Shared simulation + settlement logic for both initial processing and retries.

    Simulation outcomes (as per spec):
        < 0.70 → success  (70%)
        < 0.90 → failure  (20%)
        else   → stuck    (10%)
    """
    outcome = random.random()

    if outcome < 0.70:
        # --- Success path ---
        with transaction.atomic():
            payout.refresh_from_db()
            mark_completed(payout)

    elif outcome < 0.90:
        # --- Failure path: mark failed + refund in same transaction ---
        payout.refresh_from_db()
        mark_failed_with_refund(payout)

    else:
        # --- Stuck path: do nothing ---
        # The retry scheduled task will detect this payout as stuck
        # (processing for > 30s) and re-enqueue or give up.
        logger.warning(
            "Payout %s simulated as stuck — awaiting retry (attempt %d)",
            payout.id, payout.attempts,
        )


def process_payout(payout_id: int) -> None:
    """
    Initial async payout processing task. Only accepts pending payouts.

    State machine enforced:  pending → processing → completed | failed
    """
    try:
        payout = Payout.objects.get(id=payout_id)
    except Payout.DoesNotExist:
        logger.error("process_payout: payout %s not found", payout_id)
        return

    # Guard: only process pending payouts
    if payout.status != Payout.Status.PENDING:
        logger.warning(
            "process_payout: payout %s is '%s', expected 'pending' — skipping",
            payout_id, payout.status,
        )
        return

    # Transition pending → processing (increments attempts counter)
    mark_processing(payout)

    _simulate_and_settle(payout)


def retry_payout(payout_id: int) -> None:
    """
    Retry task for payouts stuck in 'processing'.

    Unlike process_payout, this accepts a payout already in processing state —
    it does NOT call mark_processing again (attempts was already incremented
    by the original process_payout call). It simply re-runs the simulation.

    This is called by retry_stuck_payouts() in services.py.
    """
    try:
        payout = Payout.objects.get(id=payout_id)
    except Payout.DoesNotExist:
        logger.error("retry_payout: payout %s not found", payout_id)
        return

    # Guard: only retry payouts that are still processing
    if payout.status != Payout.Status.PROCESSING:
        logger.warning(
            "retry_payout: payout %s is '%s', not 'processing' — skipping",
            payout_id, payout.status,
        )
        return

    logger.info("retry_payout: retrying payout %s (attempt %d)", payout_id, payout.attempts)
    _simulate_and_settle(payout)


def run_retry_stuck_payouts() -> None:
    """
    Scheduled task wrapper — called by Django-Q schedule every minute.
    Delegates to services.retry_stuck_payouts().
    """
    from .services import retry_stuck_payouts
    retry_stuck_payouts()
