# Payout Engine — Setup Guide

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+ running locally

---

## 1. PostgreSQL Setup

```sql
CREATE DATABASE payout_engine;
CREATE USER postgres WITH PASSWORD 'postgres';
GRANT ALL PRIVILEGES ON DATABASE payout_engine TO postgres;
```

> Or set the `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
> environment variables to match your local PostgreSQL instance.

---

## 2. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

# Install dependencies
pip install -r requirements.txt

# Apply migrations
python manage.py migrate

# Seed sample merchants (optional but recommended)
python manage.py seed_data

# Create Django admin user (optional)
python manage.py createsuperuser
```

---

## 3. Run the Backend

Open **two separate terminals**:

**Terminal 1 — API server:**
```bash
cd backend
venv\Scripts\activate
python manage.py runserver
```

**Terminal 2 — Async worker:**
```bash
cd backend
venv\Scripts\activate
python manage.py qcluster
```

> The API server handles HTTP requests.
> The qcluster worker processes payout jobs from the DB queue.
> Both must be running for end-to-end payout flow.

---

## 4. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## 5. Run Tests

```bash
cd backend
venv\Scripts\activate
python manage.py test app.tests
```

Tests:
1. **ConcurrencyTest** — 5 threads race to payout; only 1 succeeds
2. **IdempotencyTest** — same key sent twice; identical response, 1 DB row

---

## 6. Environment Variables (optional overrides)

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | dev key | Django secret key |
| `DJANGO_DEBUG` | `True` | Debug mode |
| `DB_NAME` | `payout_engine` | PostgreSQL database name |
| `DB_USER` | `postgres` | PostgreSQL user |
| `DB_PASSWORD` | `postgres` | PostgreSQL password |
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/merchants` | List all merchants |
| `GET` | `/api/v1/dashboard?merchant_id=<id>` | Balance + history |
| `POST` | `/api/v1/payouts?merchant_id=<id>` | Create payout |

**POST /api/v1/payouts headers:**
```
Idempotency-Key: <UUID>
Content-Type: application/json
```

**POST /api/v1/payouts body:**
```json
{
  "amount_paise": 5000,
  "bank_account_id": "HDFC_001"
}
```

---

## Project Structure

```
Payout Assignment/
├── backend/
│   ├── config/         Django project config (settings, urls, wsgi)
│   ├── app/            Django app (models, services, tasks, views, tests)
│   ├── manage.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/        Axios client
│   │   ├── components/ Dashboard, PayoutForm, PayoutHistory
│   │   ├── App.jsx     App shell + polling
│   │   └── main.jsx
│   ├── index.html
│   └── package.json
├── EXPLAINER.md        Design decisions
└── README.md
```
