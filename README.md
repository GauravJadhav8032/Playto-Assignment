# Payout Engine — Setup Guide

> **Playto Payout Engine** — Django 5 + DRF + Django-Q + React + Tailwind  
> Guarantees ACID consistency, race-condition prevention, and idempotent APIs.

---


## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, Django 5, Django REST Framework |
| Database | **SQLite** (local dev) · PostgreSQL (production) |
| Async Worker | Django-Q2 (ORM broker — no Redis) |
| Frontend | React 18 (Vite) + Tailwind CSS |

---

## Prerequisites

- Python 3.11+
- Node.js 18+

> **No PostgreSQL required for local development.**  
> The project uses **SQLite** out of the box via the `USE_SQLITE=1` environment variable.  
> Switch to PostgreSQL in production by unsetting that variable and providing `DB_*` env vars.

---

## 1. Backend Setup

```powershell
cd backend

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

# Install dependencies
pip install -r requirements.txt

# Apply migrations (SQLite — no DB server needed)
$env:USE_SQLITE="1"
python manage.py migrate

# Seed sample merchants with balances
python manage.py seed_data

# Register the retry-stuck-payouts schedule
python manage.py setup_schedules

# (Optional) Create Django admin user
python manage.py createsuperuser
```

---

## 2. Run the Project

Open **3 separate terminals**:

**Terminal 1 — Django API server:**
```powershell
cd backend
$env:USE_SQLITE="1"
venv\Scripts\python.exe manage.py runserver
```

**Terminal 2 — Django-Q async worker:**
```powershell
cd backend
$env:USE_SQLITE="1"
venv\Scripts\python.exe manage.py qcluster
```

**Terminal 3 — React frontend:**
```powershell
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

> Both the API server and the qcluster worker must be running for end-to-end payout flow.  
> The qcluster processes async payout jobs and retries stuck ones every 60 seconds.

---

## 3. Run Tests

```powershell
cd backend
$env:USE_SQLITE="1"
venv\Scripts\python.exe manage.py test app.tests
```

| Test | What it verifies |
|---|---|
| `ConcurrencyTest` | 5 threads race to payout the same balance — only 1 succeeds |
| `IdempotencyTest` | Same `Idempotency-Key` sent twice — identical response, 1 DB row |

---

## 4. Environment Variables

| Variable | Default | Description |
|---|---|---|
| `USE_SQLITE` | `0` | Set to `1` to use SQLite instead of PostgreSQL |
| `DJANGO_SECRET_KEY` | dev key | Django secret key (override in production) |
| `DJANGO_DEBUG` | `True` | Debug mode |
| `DB_NAME` | `payout_engine` | PostgreSQL database name |
| `DB_USER` | `postgres` | PostgreSQL user |
| `DB_PASSWORD` | `postgres` | PostgreSQL password |
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |

### Switching to PostgreSQL

```powershell
# 1. Create the database
psql -U postgres -c "CREATE DATABASE payout_engine;"

# 2. Run without USE_SQLITE (defaults to PostgreSQL)
cd backend
venv\Scripts\python.exe manage.py migrate
venv\Scripts\python.exe manage.py seed_data
venv\Scripts\python.exe manage.py setup_schedules
venv\Scripts\python.exe manage.py runserver
```

---

## 5. API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/merchants` | List all merchants |
| `GET` | `/api/v1/dashboard?merchant_id=<id>` | Balance + transaction + payout history |
| `POST` | `/api/v1/payouts?merchant_id=<id>` | Create a payout |

**POST /api/v1/payouts — required header:**
```
Idempotency-Key: <UUID>
Content-Type: application/json
```

**POST /api/v1/payouts — body:**
```json
{
  "amount_paise": 5000,
  "bank_account_id": "HDFC_001"
}
```

**GET /api/v1/dashboard — response shape:**
```json
{
  "available_balance": 495000,
  "held_balance": 5000,
  "transactions": [...],
  "payouts": [...]
}
```

---

## 6. Project Structure

```
Payout Assignment/
├── backend/
│   ├── config/                   Django project (settings, urls, wsgi)
│   ├── app/
│   │   ├── models.py             Merchant, LedgerEntry, Payout, IdempotencyKey
│   │   ├── services.py           All business logic (locking, balance, state machine)
│   │   ├── tasks.py              Async tasks: process_payout, retry_payout
│   │   ├── views.py              Thin API views
│   │   ├── tests.py              Concurrency + idempotency tests
│   │   └── management/commands/
│   │       ├── seed_data.py      Seed sample merchants
│   │       └── setup_schedules.py  Register retry schedule in Django-Q
│   ├── manage.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/client.js         Axios API wrapper
│   │   ├── components/
│   │   │   ├── Dashboard.jsx     Balance cards + transaction list
│   │   │   ├── PayoutForm.jsx    Payout submission form
│   │   │   └── PayoutHistory.jsx Status-icon table (auto-polls every 4s)
│   │   ├── App.jsx               App shell + merchant selector
│   │   └── main.jsx
│   ├── index.html
│   └── package.json
├── EXPLAINER.md                  Design decisions (ledger, locking, idempotency, AI audit)
└── README.md
```

---

## Key Design Decisions

See **[EXPLAINER.md](./EXPLAINER.md)** for full technical reasoning covering:
1. Ledger design — why append-only, balance query
2. Concurrency — how `select_for_update()` prevents overdraw
3. Idempotency — DB-level uniqueness + in-flight race handling
4. State machine — where invalid transitions are blocked in code
5. AI audit — a real bug caught and fixed during development
