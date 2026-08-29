# WarrantyOS

AI-assisted warranty & returns arbiter for electronics/appliance brands. Rules and the
database decide eligibility; AI reads evidence and recommends; every denial, high-value,
low-confidence, or conflicting claim goes to a human before it's final.

This is now through **Part 1.2** of the build: project structure + frontend/backend
shells + database schema (Phase 1), real authentication with role-based access (Phase 2),
and now a functional deterministic warranty claim platform (Part 1.2).
See `/docs/ARCHITECTURE.md` for the complete architecture, API list, route map, and phase plan.

## What works right now

- The FastAPI backend boots, connects to PostgreSQL (or SQLite fallback for local dev without Docker), and creates every table in the schema
- A `/health` endpoint and a `/api/ping-db` endpoint you can hit to prove the stack is wired up
- **Real authentication**: `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`,
  backed by bcrypt password hashing and JWTs. Customer self-signup is public; admin accounts
  are seeded (see below) rather than self-registered.
- **Deterministic warranty workflow (Part 1.2)**: customers select owned products, submit claims with serial/fault, `WarrantyRuleEngine` evaluates eligibility (product/ownership/purchase date/policy/exclusions), claim is created transactionally with timeline events, evidence can be uploaded securely, status moves through a centralized state machine.
- **Claim APIs**: `POST /api/claims`, `GET /api/claims`, `GET /api/claims/{id}`, `POST /api/claims/{id}/evidence`, `GET /api/claims/{id}/evidence`, `GET /api/claims/{id}/timeline`, `PATCH /api/claims/{id}/status`, plus `GET /api/products` and `GET /api/products/serials/mine` for owned products. All customer endpoints enforce IDOR (customer can only access own claims).
- **Admin claim queue**: `GET /api/admin/claims` (filterable by status/product/customer/date) and `GET /api/admin/claims/{id}` expose customer/product/serial/warranty result/evidence/timeline.
- **Secure file upload**: local filesystem (`./uploads/<claim_id>/`), MIME/size validation, path-traversal prevention, randomized filenames, metadata stored in PostgreSQL.
- The React frontend's login, admin-login, and register forms call these endpoints for real —
  wrong passwords show a real error, successful logins redirect into the (still placeholder)
  dashboards, and the session persists across a page refresh.
- Every `/customer/*` and `/admin/*` route is protected: signed-out visitors get bounced to the
  right login page, and a customer account can't reach admin routes (or vice versa).
- The landing page's status dot in the top-right actually calls `/api/ping-db` — if it's
  green, your backend and database are both reachable

No AI is executed yet — `WarrantyRuleEngine` is deterministic, no `RocketRide` calls, no fake dashboard numbers. All claim data is real PostgreSQL records (7 seeded claims across all states).

### Demo accounts (created by `python seed.py`)

| Role     | Email                          | Password        |
|----------|---------------------------------|-----------------|
| Customer | `demo.customer@warrantyos.com`  | `DemoPass123!`  |
| Admin    | `demo.admin@warrantyos.com`     | `DemoPass123!`  |

The login screen also has a **"Use demo customer/admin account"** button that fills these in
and submits automatically — the fastest way to see the auth flow work end to end.

## Prerequisites

You'll need these installed once:
- **Node.js** (v18+) — runs the frontend. Check with `node -v`.
- **Python** (3.11+) — runs the backend. Check with `python3 --version`.
- **Docker Desktop** — runs PostgreSQL without installing it yourself. Check with `docker -v`.

If you don't want to use Docker, you can install PostgreSQL locally instead — just update
`DATABASE_URL` in your `.env` to point at it.

## 1. Get the database running

From the repo root:

```bash
cp .env.example .env
docker compose up -d db
```

This starts a Postgres container on port 5432 with a database called `warrantyos`. Leave it
running in the background — `docker compose down` stops it later.

## 2. Run the backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

What this does: creates an isolated Python environment (`venv`), installs FastAPI/SQLAlchemy/etc,
then starts the API on `http://localhost:8000`. On startup it automatically creates every table
from `/database/schema.sql` if they don't already exist.

**Test it worked:**
```bash
curl http://localhost:8000/health        # {"status":"ok",...}
curl http://localhost:8000/api/ping-db   # {"status":"ok","database":"connected"}
```
Or just open `http://localhost:8000/docs` in a browser — FastAPI auto-generates an
interactive API explorer there, including the new `/api/auth/*` endpoints.

**Seed starter data + demo accounts:**
```bash
python seed.py
```
This creates the three roles, 5 products (Washing Machine, Refrigerator, AC, Microwave, TV), 3 warranty policies per category, 3 retailers, 10 product serials with ownership, 4 customers (demo + 3 synthetic), and 7 claims spanning `SUBMITTED, PROCESSING, UNDER_REVIEW, APPROVED, REJECTED, MORE_INFORMATION_REQUIRED, RESOLVED` with warranty eligibility varied (VALID, EXPIRED, EXCLUDED). Safe to re-run — it skips anything that already exists (idempotent).

**Test auth + claim workflow with curl** (optional — the frontend does this for you):
```bash
# login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo.customer@warrantyos.com","password":"DemoPass123!"}'
# -> {"access_token": "...", "user": {"role":"customer"}}

# list owned products/serials
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/products/serials/mine

# create claim (customer owns WMX-98234)
curl -X POST http://localhost:8000/api/claims \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"product_id":1,"serial_number":"WMX-98234","fault_description":"Motor grinding noise for 2 days, drum not spinning","fault_category":"motor"}'
# -> {"claim_code":"WR-10008","warranty_eligible":true,"eligibility_reason":"VALID..."}

# upload evidence
curl -X POST http://localhost:8000/api/claims/1/evidence \
  -H "Authorization: Bearer <token>" -F "file=@invoice.pdf" -F "evidence_type=INVOICE"

# admin queue (admin token)
curl -H "Authorization: Bearer <admin_token>" http://localhost:8000/api/admin/claims?status=SUBMITTED
```

## 3. Run the frontend

In a new terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the URL it prints (usually `http://localhost:5173`). The dev server proxies any request
to `/api/*` through to the backend on port 8000, so the two talk to each other with no extra
config.

## Project layout

```
/backend       FastAPI app — routers, models, services, core (config/db/security)
/frontend      React + TypeScript + Tailwind — pages, components, routing
/rocketrider   Isolated AI pipeline adapter (mock implementation; see its README)
/database      schema.sql — full relational schema
/docs          ARCHITECTURE.md — architecture, API list, route map, phase plan
```

## What's next (Part 2)

Part 1.2 is the deterministic foundation for intelligence. Part 2 will plug in:
`RocketRide` mock/real pipeline (`rocketrider/adapter.py`), AI-generated recommendations with confidence/evidence, risk scoring, fraud detection, fault intelligence, human-review automation, repair/replace/refund actions, analytics + dashboards — all consuming the claim/timeline/evidence structures built here without changing the warranty core.

The claim state machine, `WarrantyRuleEngine`, and secure storage abstractions are designed to be `AI-agnostic` so Part 2 can layer on top cleanly.
