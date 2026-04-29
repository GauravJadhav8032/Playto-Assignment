"""
Tests for the Payout Engine.

Test 1: Concurrency — two simultaneous payout requests, only one succeeds.
Test 2: Idempotency — same key sent twice, identical response, no duplicate row.
"""

import uuid
import threading
from django.test import TestCase, TransactionTestCase

from .models import Merchant, LedgerEntry, Payout, IdempotencyKey
from .services import create_payout, InsufficientFundsError


def _seed_merchant(name: str, credit_paise: int) -> Merchant:
    """Helper: create merchant with an initial credit ledger entry."""
    merchant = Merchant.objects.create(name=name)
    LedgerEntry.objects.create(
        merchant=merchant,
        type=LedgerEntry.EntryType.CREDIT,
        amount_paise=credit_paise,
        reference="initial_seed",
    )
    return merchant


# ---------------------------------------------------------------------------
# Test 1: Concurrency
# ---------------------------------------------------------------------------

class ConcurrencyTest(TransactionTestCase):
    """
    Use TransactionTestCase (not TestCase) because concurrent threads need to
    see committed data across separate DB connections — TestCase wraps
    everything in a single non-committed transaction that other threads can't see.
    """

    def test_only_one_payout_succeeds_under_concurrency(self):
        """
        Spawn 5 threads that each try to create a payout of 10,000 paise
        against a balance of 10,000 paise.
        Expected: exactly 1 payout created; ledger balance == 0.
        """
        merchant = _seed_merchant("Concurrent Merchant", credit_paise=10_000)
        amount = 10_000
        successes = []
        failures = []
        lock = threading.Lock()

        def attempt_payout():
            key = uuid.uuid4()  # Each thread uses a unique idempotency key
            try:
                result = create_payout(
                    merchant_id=merchant.id,
                    amount_paise=amount,
                    bank_account_id="bank_test_123",
                    idempotency_key=key,
                )
                with lock:
                    successes.append(result)
            except InsufficientFundsError as exc:
                with lock:
                    failures.append(str(exc))

        threads = [threading.Thread(target=attempt_payout) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Only one payout should have been created
        payout_count = Payout.objects.filter(merchant=merchant).count()
        self.assertEqual(len(successes), 1, f"Expected 1 success, got {len(successes)}")
        self.assertEqual(payout_count, 1, f"Expected 1 Payout row, got {payout_count}")

        # Remaining 4 requests should have failed with InsufficientFundsError
        self.assertEqual(len(failures), 4, f"Expected 4 failures, got {len(failures)}")


# ---------------------------------------------------------------------------
# Test 2: Idempotency
# ---------------------------------------------------------------------------

class IdempotencyTest(TestCase):

    def test_same_idempotency_key_returns_same_response_no_duplicate(self):
        """
        Send the same Idempotency-Key twice.
        Expected:
          - Both calls return identical response dicts.
          - Only one Payout row exists.
          - Only one IdempotencyKey row exists.
        """
        merchant = _seed_merchant("Idempotency Merchant", credit_paise=50_000)
        key = uuid.uuid4()
        amount = 5_000

        response_1 = create_payout(
            merchant_id=merchant.id,
            amount_paise=amount,
            bank_account_id="bank_idem_456",
            idempotency_key=key,
        )

        response_2 = create_payout(
            merchant_id=merchant.id,
            amount_paise=amount,
            bank_account_id="bank_idem_456",
            idempotency_key=key,
        )

        # Responses must be identical
        self.assertEqual(response_1, response_2, "Responses differ — idempotency broken")

        # Exactly one payout row
        payout_count = Payout.objects.filter(merchant=merchant).count()
        self.assertEqual(payout_count, 1, f"Expected 1 Payout, got {payout_count}")

        # Exactly one idempotency key row
        idem_count = IdempotencyKey.objects.filter(merchant=merchant, key=key).count()
        self.assertEqual(idem_count, 1, f"Expected 1 IdempotencyKey, got {idem_count}")
