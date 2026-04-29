# EXPLAINER.md — Payout Engine Design Decisions

---

## 1. The Ledger

### Balance Calculation Query

**Django ORM (services.py → `_compute_balance_db`)**


```python
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
balance = result["total_credit"] - result["total_debit"]
```

**Equivalent SQL:**
```sql
SELECT
  COALESCE(SUM(CASE WHEN type = 'CREDIT' THEN amount_paise END), 0) -
  COALESCE(SUM(CASE WHEN type = 'DEBIT'  THEN amount_paise END), 0)
FROM ledger_entries
WHERE merchant_id = %s;
```

### Why model credits and debits this way?

Two reasons:

**Append-only correctness.** A stored balance column is a mutable summary of history. Any bug, crash, or race condition that updates it incorrectly silently corrupts the merchant's money. An append-only ledger means the source of truth is always the raw entries — balance is a derived view, never an authoritative state. You cannot accidentally overdraw someone by updating the wrong row.

**Auditability.** Every paise movement has a timestamped, immutable record with a `reference` string explaining why. A `DEBIT` for `payout_hold:HDFC_001` and a `CREDIT` for `refund:payout_7` tell a complete story. A balance column tells you nothing about how you got there.

---

## 2. The Lock

### Exact code that prevents concurrent overdraw

**`services.py` → `create_payout()`**

```python
with transaction.atomic():
    # Acquires SELECT ... FOR UPDATE on every ledger row for this merchant.
    # Any concurrent transaction attempting the same lock will BLOCK here
    # until this transaction commits or rolls back.
    LedgerEntry.objects.select_for_update().filter(merchant_id=merchant_id)

    # Balance is computed INSIDE the lock — reads the locked, committed state.
    balance = _compute_balance_db(merchant_id)

    if balance < amount_paise:
        raise InsufficientFundsError(
            f"Insufficient balance: available={balance}, requested={amount_paise}"
        )

    # Both writes happen atomically inside the same lock scope.
    LedgerEntry.objects.create(type=LedgerEntry.EntryType.DEBIT, ...)
    Payout.objects.create(status=Payout.Status.PENDING, ...)
```

### Database primitive

**PostgreSQL row-level exclusive lock (`SELECT ... FOR UPDATE`)**

When Transaction A executes `select_for_update()`, PostgreSQL acquires an exclusive lock on those rows. Transaction B attempting the same `select_for_update()` on the same merchant's rows **blocks** — it waits, not reads stale data. By the time B acquires the lock, A has already committed the DEBIT, so B's `_compute_balance_db()` sees the updated balance and correctly raises `InsufficientFundsError`.

Without this lock, both transactions could read the same pre-debit balance simultaneously, both pass the `balance >= amount` check, and both insert DEBIT entries — classic overdraw race condition.

---

## 3. The Idempotency

### How the system recognises a seen key

Every payout request carries an `Idempotency-Key: <UUID>` header. Before any transaction opens, the service queries:

```python
# services.py → create_payout()
try:
    cached = IdempotencyKey.objects.get(merchant_id=merchant_id, key=idempotency_key)
    return cached.response   # return stored JSON immediately, no DB writes
except IdempotencyKey.DoesNotExist:
    pass                     # first time — proceed
```

At the end of the transaction, the full response JSON is persisted:

```python
IdempotencyKey.objects.create(
    merchant_id=merchant_id,
    key=idempotency_key,
    response=response_data,   # full JSON stored for replay
)
```

The `IdempotencyKey` table has a **DB-level `UNIQUE(merchant_id, key)` constraint** — not just application-level uniqueness.

### What happens if the first request is still in-flight when the second arrives

Both requests pass the initial `objects.get()` check (the row doesn't exist yet). Both enter `transaction.atomic()` and both attempt `IdempotencyKey.objects.create()`. The database constraint ensures only one `INSERT` succeeds. The other transaction gets an `IntegrityError` (unique violation), which is caught:

```python
try:
    IdempotencyKey.objects.create(merchant_id=..., key=..., response=...)
except Exception:
    # The concurrent request won the INSERT race.
    # Fetch its stored response and return it — same result, no duplicate payout.
    cached = IdempotencyKey.objects.get(merchant_id=merchant_id, key=idempotency_key)
    return cached.response
```

The loser fetches the winner's response and returns it. Both callers receive identical JSON. One `Payout` row exists. One `IdempotencyKey` row exists. The DB constraint is the final safety net — application logic alone is not enough under concurrency.

---

## 4. The State Machine

### Where failed → completed is blocked

**`models.py` — transition map co-located with the model:**

```python
class Payout(models.Model):
    VALID_TRANSITIONS: dict[str, list[str]] = {
        "pending":    ["processing"],
        "processing": ["completed", "failed"],
        # "completed" and "failed" are intentionally absent.
        # dict.get() returns [] for missing keys — no transitions allowed.
    }
```

**`services.py` — enforced before every status write:**

```python
def _assert_valid_transition(payout: Payout, target_status: str) -> None:
    allowed = Payout.VALID_TRANSITIONS.get(payout.status, [])
    if target_status not in allowed:
        raise InvalidTransitionError(
            f"Cannot transition payout {payout.id} "
            f"from '{payout.status}' to '{target_status}'"
        )
```

For a `failed` payout: `VALID_TRANSITIONS.get("failed", [])` → `[]`. Any target status — including `"completed"` — is not in `[]`, so `InvalidTransitionError` is raised. The write never reaches the database.

This function is called inside `mark_processing`, `mark_completed`, and `mark_failed_with_refund`. Every status write goes through it — there is no bypass path.

---

## 5. The AI Audit

### What the AI wrote

When implementing the retry mechanism for stuck payouts, the AI generated this in `services.py`:

```python
# AI-generated — subtly broken
def retry_stuck_payouts():
    for payout in stuck_payouts:
        if payout.attempts < 3:
            async_task("app.tasks.process_payout", payout.id)  # ← the bug
        else:
            mark_failed_with_refund(payout)
```

And in `tasks.py`:

```python
# AI-generated process_payout
def process_payout(payout_id):
    payout = Payout.objects.get(id=payout_id)

    # Guard that silently kills the retry:
    if payout.status != Payout.Status.PENDING:  # ← stuck payout is PROCESSING, not PENDING
        logger.warning("skipping")
        return   # silent no-op — payout stays stuck forever
    ...
```

### What I caught

The retry enqueues `process_payout`. But `process_payout` guards against non-`pending` status and silently returns if the payout is `processing`. A stuck payout **is** in `processing` state. So every retry cycle: scheduler fires → enqueues `process_payout` → worker picks it up → status is `processing` → guard triggers → returns silently → payout stays stuck forever. No error, no log that indicates failure, funds locked indefinitely.

This was confirmed live — a payout sat in `processing` state and never resolved across multiple retry cycles.

### What I replaced it with

Created a separate `retry_payout` task in `tasks.py` that explicitly accepts `processing`-state payouts:

```python
def retry_payout(payout_id: int) -> None:
    payout = Payout.objects.get(id=payout_id)

    # Correctly guards for PROCESSING — not PENDING
    if payout.status != Payout.Status.PROCESSING:
        logger.warning("retry_payout: payout %s is '%s', not 'processing' — skipping",
                       payout_id, payout.status)
        return

    logger.info("retry_payout: retrying payout %s (attempt %d)", payout_id, payout.attempts)
    _simulate_and_settle(payout)   # shared simulation — no mark_processing call
```

Updated `retry_stuck_payouts` to call `retry_payout` instead:

```python
async_task("app.tasks.retry_payout", payout.id)  # ← correct
```

The distinction matters: `process_payout` owns the `pending → processing` transition (calls `mark_processing`). `retry_payout` picks up from an already-processing state and runs simulation directly — consistent with the state machine. The fix was verified: the next retry cycle resolved the stuck payout to `completed`.
