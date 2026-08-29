# WarrantyOS — Architecture

AI-assisted warranty & returns arbiter for electronics/appliance brands.
Hybrid decisioning: **deterministic rules + database facts decide eligibility, AI explains and
recommends, humans approve every denial and every high-risk case.**

## A. Recommended Architecture

```
┌─────────────┐      HTTPS/JSON      ┌──────────────────┐      SQL      ┌────────────┐
│  Frontend   │  ───────────────►    │  Backend (API)   │  ─────────►  │ PostgreSQL │
│  React+TS   │  ◄───────────────    │  FastAPI          │  ◄─────────  │  Database  │
└─────────────┘                      └────────┬─────────┘               └────────────┘
                                               │
                                     calls adapter, never
                                     the vendor SDK directly
                                               ▼
                                     ┌──────────────────────┐
                                     │ RocketRide Adapter    │  (rocketrider/)
                                     │ pipeline orchestrator │
                                     │  - stage 1..7 steps   │
                                     │  - MOCK impl included │
                                     │  - swap in real SDK   │
                                     │    behind same interface
                                     └──────────────────────┘
```

Layering inside the backend:
- **routers/** — HTTP boundary only (auth, claims, admin, products, analytics…)
- **schemas/** — Pydantic request/response contracts
- **services/** — business logic: `warranty_rules.py` (deterministic), `risk_engine.py`
  (rule-based suspicious-claim scoring), `claim_workflow.py` (orchestrates the pipeline),
  `ai_service.py` (thin wrapper that calls the RocketRide adapter and shapes its output)
- **models/** — SQLAlchemy ORM tables, one module per bounded concept
- **core/** — config, security (hashing/JWT), db session

This separation is what makes "AI recommends, rules decide" enforceable in code: the AI
service can *only* return a `recommendation + confidence + evidence` object; only
`claim_workflow.py` is allowed to write a final `claim_decisions` row, and it always runs
the recommendation through `validate_recommendation()` (deterministic) before anything is
considered final.

## B. Folder Structure

```
/warrantyos
  /backend
    /app
      /core       -> config.py, security.py, database.py
      /models     -> SQLAlchemy models (one file per domain group)
      /schemas    -> Pydantic schemas
      /routers    -> auth, claims, admin, products, policies, analytics, notifications
      /services   -> warranty_rules, risk_engine, claim_workflow, ai_service, storage
      main.py
    requirements.txt
    seed.py
    Dockerfile
  /frontend
    /src
      /pages      -> route-level screens
      /components -> shared UI (Badge, Card, Timeline, FileDropzone, Sidebar…)
      /layouts    -> CustomerLayout, AdminLayout
      /lib        -> api client, auth context
      /types      -> shared TS types
    package.json
    vite.config.ts
    tailwind.config.js
  /rocketrider
    adapter.py     -> RocketRideClient interface + MOCK implementation
    pipeline.py    -> the 7-stage orchestration contract
    README.md      -> exactly where to plug in the real SDK
  /database
    schema.sql      -> full relational schema, hand-readable
  /docs
    ARCHITECTURE.md (this file)
  docker-compose.yml
  .env.example
  README.md
```

## C. Database Schema (summary — full DDL in `/database/schema.sql`)

Core tables (22, matching the spec): `users`, `roles`, `customers`, `admins`, `products`,
`product_serials`, `retailers`, `warranty_policies`, `claims`, `claim_evidence`,
`claim_analysis`, `claim_decisions`, `claim_reviews`, `claim_timeline`, `repair_orders`,
`replacement_orders`, `inventory`, `notifications`, `historical_cases`, `fault_events`,
`production_batches`, `risk_flags`, `audit_logs`.

Key relationships:
- `product_serials.product_id → products.id`, `product_serials.batch_id → production_batches.id`
- `claims.customer_id / product_id / serial_id / retailer_id` → respective tables
- `claims.id` fans out into `claim_evidence`, `claim_analysis`, `claim_decisions`,
  `claim_reviews`, `claim_timeline`, `risk_flags` (1-to-many)
- `fault_events` aggregate from `claims` for a `product_id` + `batch_id`, driving the
  Fault Intelligence and batch-alert screens.

## D. API List (Part 1.2 implemented — no AI yet)

```
POST   /api/auth/register
POST   /api/auth/login              (customer + admin, role in response)
GET    /api/auth/me

POST   /api/claims                  create claim (customer, warranty-checked)
GET    /api/claims                  list own (customer) or all (admin/support) — ?status= filter
GET    /api/claims/{id}             detail with product/serial/customer/warranty/evidence/timeline (IDOR-protected)
POST   /api/claims/{id}/evidence    upload INVOICE|PHOTO|VIDEO|OTHER (multipart, secure)
GET    /api/claims/{id}/evidence    list evidence metadata
GET    /api/claims/{id}/timeline    audit trail
PATCH  /api/claims/{id}/status      centralized transition (role-gated)

GET    /api/products                list active products
GET    /api/products/serials/mine   owned serials for current customer
GET    /api/products/{id}           product + warranty policy

GET    /api/admin/claims            admin queue — ?status=&product_id=&customer_id=&date_from=&date_to=
GET    /api/admin/claims/{id}       admin detail (full warranty/evidence/timeline)

GET    /health
GET    /api/ping-db
```

### D1. Claim Lifecycle (Part 1.2)

```
Customer selects owned Product/Serial
  → POST /api/claims {product_id, serial_number, fault_description, fault_category, purchase_date?}
  → WarrantyRuleEngine evaluates (product/ownership/purchase date/policy/exclusions)
  → Claim row created (SUBMITTED) + CLAIM_CREATED + WARRANTY_CHECKED timeline (transactional)
  → Customer uploads evidence POST /api/claims/{id}/evidence (INVOICE/PHOTO/VIDEO/OTHER)
  → EVIDENCE_UPLOADED timeline; if status was MORE_INFORMATION_REQUIRED → auto PROCESSING
  → Admin lists via GET /api/admin/claims, inspects detail GET /api/admin/claims/{id}
  → Status moves via PATCH /api/claims/{id}/status through centralized machine
```

### D2. State Machine (centralized `app/services/status_machine.py`)

```
SUBMITTED ──→ PROCESSING
PROCESSING ─┬→ UNDER_REVIEW
            ├→ APPROVED ──→ RESOLVED
            ├→ REJECTED (terminal)
            └→ MORE_INFORMATION_REQUIRED ──→ PROCESSING (customer provides info)

UNDER_REVIEW ─┬→ APPROVED / REJECTED / MORE_INFORMATION_REQUIRED
APPROVED ──→ RESOLVED
REJECTED, RESOLVED: terminal (no outgoing)
```

All transitions go through `assert_valid_transition()`; invalid → 409. Customers only allowed `MORE_INFORMATION_REQUIRED→PROCESSING`; admins can perform any valid edge.

### D3. WarrantyRuleEngine (`app/services/warranty_rules.py`)

Deterministic, no LLM. Inputs: product, serial, policy, customer_id, fault_desc/cat, purchase_date. Outputs: `{eligible, warranty_active, policy_match, reason, exclusions_triggered, missing_information, purchase_date, warranty_end_date}`.

Rules evaluated in order: product exists → serial exists & belongs to product → ownership → purchase date valid → policy exists → warranty period not expired (`purchase_date + warranty_months`) → exclusions (`not_covered` substring in fault text) → missing info. Reasons are `VALID`, `EXPIRED`, `INVALID_PRODUCT`, `OWNERSHIP_MISMATCH`, `MISSING_INFORMATION`, `EXCLUDED`.

### D4. Evidence Storage (`app/services/storage.py`)

`UPLOAD_DIR` (`./backend/uploads`), `MAX_UPLOAD_MB=20`. Allowed MIME: `image/jpeg|png|webp|heic`, `application/pdf`, `video/mp4|quicktime`, `text/plain` + extension fallback. Security: `Path(filename).name` sanitization, `uuid4` stored names (`<claim_id>/<uuid>.<ext>`), `relative_to` traversal check, streaming size enforcement → 413, never trust user filename, never expose absolute path, metadata (`original_filename`, `stored_filename`, `mime_type`, `file_size`, `uploaded_by`) stored in `claim_evidence`. Storage abstraction (`save_upload`/`delete_file`) allows future S3/GCS swap.

### D5. Authorization

- `GET /api/claims` customer → `WHERE customer_id = me`; admin/support → all.
- `GET /api/claims/{id}` / `evidence` / `timeline` / `PATCH status` / `POST evidence` → `_verify_claim_access` (IDOR): if role `admin|support` allow, else must own claim via `Customer.user_id`.
- `POST /api/claims` requires `customer` role (`require_role("customer")`).
- `GET /api/admin/claims` requires `admin|support`.
- Frontend `ProtectedRoute` is UX only; backend is source of truth.

### D6. Transactions

- `POST /api/claims`: `Claim` + `ClaimTimeline(CLAIM_CREATED,WARRANTY_CHECKED)` in single `flush()+commit`; on `IntegrityError` → 400, other → rollback.
- `POST /api/claims/{id}/evidence`: `ClaimEvidence` + `Timeline` + possible status auto-transition in one transaction; file deleted on rollback.
- Seed is idempotent via `IF NOT EXISTS` checks + `claim_code` uniqueness.

## E. Frontend Route Map

```
/                          landing
/login                     customer login
/register
/admin/login
/customer/dashboard
/customer/claims/new
/customer/claims/:id
/customer/notifications
/admin/dashboard
/admin/claims
/admin/claims/:id
/admin/reviews
/admin/products
/admin/inventory
/admin/policies
/admin/fault-intelligence
/admin/analytics
/admin/settings
```

## F. RocketRide Pipeline Design

`rocketrider/pipeline.py` defines the 7-stage contract described in the spec:

```
CLAIM INPUT → DOCUMENT EXTRACTION → WARRANTY/POLICY CHECK → EVIDENCE/VISION ANALYSIS
  → SIMILAR CASE SEARCH → DECISION AGENT → VALIDATOR → (HUMAN REVIEW IF REQUIRED) → FINAL ACTION
```

The exact RocketRide SDK/API was not available in this context, so `rocketrider/adapter.py`
defines an isolated `RocketRideClient` interface with a clearly-labeled `MockRocketRideClient`
that produces realistic, structured stage outputs (deterministic + a bit of randomness seeded
by the claim's own data, not invented "facts" about the product). Every place the real SDK
needs to be wired in is marked with `# ROCKETRIDE: connect real client here`. The backend's
`ai_service.py` only talks to the `RocketRideClient` interface, never a concrete SDK, so
swapping in the genuine RocketRide integration later is a one-file change.

## G. Development Phases

1. Project structure + frontend shell + backend shell + database ← done
2. Authentication + customer/admin roles ← done
3-5. **Part 1.2: Core Warranty Data + Claim Workflow** ← **this delivery** (deterministic, no AI)
   - Warranty domain (products, serials, policies), claim model, status machine, timeline, evidence, `WarrantyRuleEngine`, secure upload, customer/admin APIs, seed across all states
6. AI service (Part 2)
7. RocketRide pipeline integration (Part 2)
8. Validation + human review (Part 2)
9. Repair/replacement/refund actions
10. Analytics + fault intelligence
11. Suspicious claim detection
12. Polish + responsive design + demo data

After each phase you'll get: files changed, exact commands to run, and how to test it.

## H. Part 1.2 Database Relationships (summary)

- `users → roles`, `customers.user_id → users.id` (unique), `admins.user_id → users.id`
- `products` ← `production_batches` (unique `product_id+batch_code`), `warranty_policies.product_id → products.id`
- `product_serials`: `product_id → products.id`, `batch_id → production_batches.id`, `owner_customer_id → customers.id`, `sold_by_retailer_id → retailers.id`, `serial_number` unique
- `claims`: `customer_id → customers.id`, `product_id → products.id`, `serial_id → product_serials.id`, `retailer_id → retailers.id`, `purchase_date` snapshot, `warranty_eligible` + `eligibility_reason` deterministic, `status` via state machine, `exclusions_triggered`/`missing_information` arrays
- `claim_evidence`: `claim_id → claims.id`, metadata (`original_filename`, `stored_filename`, `mime_type`, `file_size`, `uploaded_by_user_id → users.id`)
- `claim_timeline`: `claim_id → claims.id`, `event_type` (`CLAIM_CREATED|WARRANTY_CHECKED|EVIDENCE_UPLOADED|STATUS_CHANGED|...`), `actor`, `notes`, `event_metadata` JSONB
- `claim_analysis/claim_decisions` reserved for Part 2 AI; `claim_reviews`, `repair_orders`, etc. unused in 1.2 but present for future.

## I. How to Seed & Test (Part 1.2)

```bash
# from warrantyos/
cp .env.example .env  # or keep sqlite for local without Docker
docker compose up -d db  # or use sqlite fallback
cd backend && python seed.py  # idempotent: 5 products, 5 policies, 10 serials, 4 customers, 7 claims
# claims: WR-20001 SUBMITTED (VALID), WR-20002 PROCESSING (VALID), WR-20003 UNDER_REVIEW (EXPIRED), WR-20004 APPROVED (VALID), WR-20005 REJECTED (EXPIRED), WR-20006 MORE_INFORMATION_REQUIRED (EXCLUDED), WR-20007 RESOLVED (VALID)
# test workflow: see README "Test auth + claim workflow with curl" and run python test_part12.py against live backend
```
