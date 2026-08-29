# WarrantyOS — Intelligence Layer Architecture (Part 2.0 Audit)

> **Status:** Architecture & integration audit only. No AI execution, no mock confidence/ recommendations. Deterministic Part 1 (auth, warranty, claims, evidence, timeline, state machine) remains untouched.

---

## 1. Current Architecture (Part 1.3 as-built)

**Stack:** React 18 + TypeScript 5 + Vite 5 + Tailwind 3 | FastAPI 0.115 + SQLAlchemy 2 + PostgreSQL 16 (SQLite fallback for local) + JWT/bcrypt | `rocketrider/` adapter abstraction.

**Backend layering is strictly separated** — this is what makes `AI recommends. Rules decide. Humans protect.` enforceable:

```
Frontend (SPA, RBAC UX only)
   │ HTTPS/JSON + Bearer JWT
   ▼
Routers (HTTP boundary only: auth, claims, admin_claims, products, system)
   │ Pydantic schemas
   ▼
Services (business logic)
   - warranty_rules.py  (deterministic, authoritative)
   - status_machine.py  (centralized, no arbitrary transitions → 409)
   - storage.py         (secure FS, future S3/GCS swappable)
   - (future) ai_service.py, claim_workflow.py, risk_engine.py
   ▼
Models (SQLAlchemy, PostgreSQL DDL is source of truth, SQLite via with_variant)
   - user/role/customer/admin, product/serial/batch/policy, claim/evidence/timeline, analysis/decision/review
   ▼
Core (config, security, database, deps)
   │ calls adapter, never vendor SDK directly
   ▼
RocketRide Adapter (rocketrider/adapter.py + pipeline.py)
   - MockRocketRideClient (deterministic + seeded randomness, no invented vendor syntax)
   - RealRocketRideClient (one-file swap, see README)
```

**Existing claim flow (Part 1.2, no AI):** `POST /api/claims` → `WarrantyRuleEngine` → `Claim (SUBMITTED)` + `ClaimTimeline(CLAIM_CREATED, WARRANTY_CHECKED)` (transactional) → `POST /api/claims/{id}/evidence` (MIME/size/traversal checks, randomized `uploads/<claim_id>/<uuid>.<ext>`) → `EVIDENCE_UPLOADED` timeline + auto `MORE_INFORMATION_REQUIRED→PROCESSING` if applicable → `PATCH /api/claims/{id}/status` (centralized machine, role-gated) → Admin queue/detail via `GET /api/admin/claims*` (IDOR-protected via `_verify_claim_access`).

**DB counts (seed idempotent):** `users/roles/customers/admins`, `5 products`, `5 warranty_policies`, `3 retailers`, `production_batches`, `10 product_serials` (ownership + purchase_date), `7 claims` across all 7 states (`WR-20001..WR-20007`), `26 timeline`, `3 evidence`.

---

## 2. RocketRide Integration — Current Status

### 2.1 SDK Installed?

**No.** `backend/requirements.txt:1` lists `fastapi, uvicorn, sqlalchemy, psycopg2-binary, pydantic*, email-validator, python-jose, passlib[bcrypt], bcrypt, python-multipart, python-dotenv` — **no `rocketride` package, no `openai` dependency is RocketRide-specific**. `pip list` on this host shows `openai 2.24.0`, `google-generativeai 0.8.6` installed globally (likely for other tooling), but **not imported or referenced anywhere in `warrantyos/`**. No `rocketride` import beyond the local `rocketrider/` folder exists.

### 2.2 Version

`UNKNOWN — REQUIRES VERIFICATION`. No SDK present, no version pinned, no lockfile. `rocketrider/README.md:3` explicitly states “The exact RocketRide SDK/API was not available in this build environment”.

### 2.3 Authentication Configured?

**No.** Placeholder only. `backend/app/core/config.py:39` `ROCKETRIDE_MODE` defaults to `"mock"`, `ROCKETRIDE_API_KEY` defaults to `""`. `.env.example:17` shows `ROCKETRIDE_MODE=mock` and empty `ROCKETRIDE_API_KEY`, with comment “Switch to `rocketride` only once the real SDK is wired in (see /rocketrider/README.md)”. No key is committed, no secret is exposed.

### 2.4 Expected Credentials / Env Vars

| Var | Required when | Where read |
|-----|---------------|------------|
| `ROCKETRIDE_MODE` | always | `config.py:40` — `"mock"` or `"rocketride"` |
| `ROCKETRIDE_API_KEY` | `mode=rocketride` | `config.py:41` |

**Unknown:** Whether RocketRide uses Bearer API key, OAuth, mTLS, `cloud.rocketride.ai` domain, or per-workspace keys — **UNKNOWN — REQUIRES VERIFICATION** (no organizer doc in repo provides this).

### 2.5 Methods Exposed (in-repo contract)

Only the **local abstraction**:

```python
class RocketRideClient(ABC):
    def run_pipeline(self, data: ClaimPipelineInput) -> ClaimPipelineResult: ...
```

- **Input:** `ClaimPipelineInput` (`claim_code`, `product_name`, `category`, `serial_number`, `fault_description`, `purchase_date`, `warranty_months`, `covered`, `not_covered`, `has_invoice`, `has_photo`, `has_video`, `customer_claim_count_90d`) — `rocketrider/pipeline.py:35`.
- **Output:** `ClaimPipelineResult` (`stage_outputs: Dict[str,Any]`, `recommendation: str`, `confidence: float`, `evidence: List[str]`, `risk_flags: List[str]`, `missing_information: List[str]`, `similar_case_count: int`) — `pipeline.py:52`.
- **Stages:** `STAGES = ["DOCUMENT_EXTRACTION","POLICY_CHECK","EVIDENCE_ANALYSIS","SIMILAR_CASE_SEARCH","DECISION_AGENT","VALIDATOR"]` (`pipeline.py:25`).

**Unknown:** Real SDK method names, endpoint paths, auth headers, pagination, streaming — **UNKNOWN**.

### 2.6 Input Format Expected

**Unknown — requires verification.** The local contract expects structured dataclass fields (strings/lists/booleans) plus boolean evidence flags (`has_invoice/photo/video`), not raw files. Whether RocketRide expects raw PDF bytes, image URLs, or `multipart/form-data` is unknown — the adapter deliberately avoids inventing vendor syntax.

### 2.7 Output Format Returned

**Unknown.** `MockRocketRideClient` (`adapter.py:38`) returns `ClaimPipelineResult` with `stage_outputs["DOCUMENT_EXTRACTION"|"POLICY_CHECK"|...]` + `recommendation ∈ {DENY,REPAIR,REPLACE,MORE_INFORMATION_REQUIRED}` + `confidence ∈ [0,0.97]` + `similar_case_count`. Real SDK output format is **UNKNOWN** — must be verified against official docs; the architecture assumes **structured JSON** will be requested via the adapter.

### 2.8 Multimodal Evidence Supported?

**Unknown — requires verification.** `ClaimEvidence` stores `mime_type` (`image/jpeg|png|webp|pdf|video/mp4` etc.) and `storage.py:13` allows multimodal ingest, but whether RocketRide accepts PDF pages, image bytes, or video frames is undocumented in-repo.

### 2.9 Can PDFs/Images Be Passed Directly?

**Current design allows it, but RocketRide acceptance is UNKNOWN.** `storage.py` saves files to `uploads/<claim_id>/<uuid>.<ext>` and `ClaimPipelineInput.has_invoice/has_photo/has_video` are booleans derived from evidence existence. For Part 2, the adapter should **pass file references or bytes read from disk**, never filesystem paths, never unrelated claims (see §11 Security). Whether RocketRide expects base64, presigned URLs, or direct upload is **UNKNOWN**.

### 2.10 Can Structured JSON Output Be Requested?

**Unknown, but strongly recommended.** The pipeline expects `Dict[str,Any]` per stage. The adapter should request `response_format={"type":"json_object"}` or equivalent if the vendor supports it, and validate via Pydantic before persisting. This must be verified against SDK.

### 2.11 Workflows / Agents Available?

**Unknown — requires verification.** `pipeline.py` models a 6-stage workflow as a design aspiration from the product spec/PPT, not as a confirmed vendor workflow primitive. Whether RocketRide exposes `agents`, `workflows`, `tools`, or must be orchestrated client-side is **UNKNOWN**.

### 2.12 Can System Execute Multiple Intelligence Stages?

**Yes — via local orchestration, even if vendor does not.** `MockRocketRideClient.run_pipeline` executes all 6 stages sequentially in one call (`adapter.py:38`). `STAGES` constant defines order. Whether this should be one vendor call or six orchestrated calls in `RealRocketRideClient` is an implementation choice to be verified against rate limits.

### 2.13 Errors RocketRide Can Return

**Unknown — requires verification.** No vendor error schema is in-repo. Expected categories to handle (see §9): network, timeout, 429, 400 (bad input), 401/403 (auth), 422 (structured output validation), 500. All must be treated as non-fatal to the deterministic flow.

### 2.14 Rate Limits / Request Constraints

**Unknown — requires verification.** No limits are documented in-repo. See §12 for conservative strategy (one analysis per claim, cached, no re-analysis unless explicit).

### 2.15 Adapter Abstraction to Preserve

**Yes — `RocketRideClient` must be preserved.** `rocketrider/adapter.py:14` is the **only** import boundary the rest of the app may depend on. `backend` must never import vendor SDK directly. `rocketrider/README.md:24` specifies the one-file swap: implement `RealRocketRideClient(RocketRideClient)` in `adapter.py` and change the import in `backend/app/services/ai_service.py` (file does not yet exist — see §4). This keeps `frontend/` and `backend/` zero-change when vendor is swapped.

---

## 3. Official RocketRide Documentation Available in Project

**None beyond the in-repo adapter contract.** Grep across `warrantyos/` for `RocketRide|cloud.rocketride.ai|api key|agent|workflow|multimodal|structured output|models` finds only:

- `rocketrider/README.md` (adapter instructions, no vendor spec)
- `rocketrider/adapter.py` + `pipeline.py` (local contracts)
- `.env.example:14` + `config.py:39` (mode/key placeholders)
- `database/schema.sql:125` comment `-- matches rocketrider pipeline stage names`
- `docs/ARCHITECTURE.md:F` (pipeline design aspiration, explicitly “exact SDK not available”)
- `README.md:137` (`/rocketrider` description)

**No PDF, no `docs/rocketride.md`, no vendor URL, no SDK import, no example auth flow, no multimodal spec.** Therefore the expected usage as **intended by the organizer** is: *use the `RocketRideClient` interface; the real SDK will be provided later; do not invent `cloud.rocketride.ai` calls*.

**Unknowns requiring organizer clarification:** See §15 Risks/Blockers.

---

## 4. Current Claim Data — What Can Support AI & What Is Missing

### 4.1 Existing Entities Useful for AI

| Entity | Key fields | AI relevance |
|--------|------------|--------------|
| `Claim` (`models/claim.py:11`) | `fault_description`, `fault_category`, `status`, `purchase_date` snapshot, `warranty_eligible`, `eligibility_reason`, `exclusions_triggered`, `missing_information` | Primary input + deterministic ground truth. `warranty_eligible` must remain authoritative. |
| `Product`, `ProductSerial`, `WarrantyPolicy` (`models/product.py:16`) | `name/sku/category`, `serial_number`, `purchase_date`, `warranty_months`, `covered/not_covered/conditions/covered_fault_categories` | Product identity, ownership, policy for stages 1-2. |
| `ClaimEvidence` (`claim.py:43`) | `evidence_type ∈ INVOICE|PHOTO|VIDEO|OTHER`, `original_filename`, `stored_filename`, `mime_type`, `file_size`, `uploaded_by_user_id`, `file_path` (`<id>/<uuid>`) | Multimodal inputs for Stage 1 & 3. Files on FS, not DB. |
| `ClaimTimeline` (`claim.py:96`) | `event_type` (`CLAIM_CREATED|WARRANTY_CHECKED|EVIDENCE_UPLOADED|STATUS_CHANGED`), `actor`, `notes`, `event_metadata JSONB` | Audit trail for every AI step; PPT expects full journey. |
| `ClaimAnalysis` (`claim.py:62`) | `claim_id FK`, `stage VARCHAR(50)` (matches `STAGES`), `result JSONB` | **Current AI write target.** Already designed to store per-stage outputs from `ClaimPipelineResult.stage_outputs`. No changes needed for stage-level persistence. |
| `ClaimDecision` (`claim.py:71`) | `recommendation`, `confidence`, `evidence TEXT[]`, `risk_flags TEXT[]`, `missing_information TEXT[]`, `requires_human_review BOOL`, `review_reason`, `final_outcome` | **Current decision write target.** `recommendation ∈ REPAIR|REPLACE|REFUND|DENY|HUMAN_REVIEW`, `confidence NUM`. |
| `ClaimReview` (`claim.py:86`) | `reviewed_by_admin_id → admins.id`, `action ∈ APPROVE|REJECT|REQUEST_MORE_INFO|ESCALATE`, `notes` | Human review. |
| `RiskFlag` (`models/intelligence.py:36`) | `claim_id`, `flag_type`, `detail`, `weight` | Normalized risk signals (vs `ClaimDecision.risk_flags` array). |
| `HistoricalCase` (`intelligence.py:16`) | `product_id`, `fault_category`, `resolution`, `summary` | Similar-case corpus (currently empty; seed has no historical cases). |
| `AuditLog` (`intelligence.py:46`) | `actor`, `action`, `entity`, `entity_id` | Cross-entity audit (could log AI calls). |

### 4.2 Gaps for Full AI Pipeline

What the schema **already supports** vs what is **missing** for the 6-stage vision:

| Needed for AI | Status | Recommendation |
|---------------|--------|----------------|
| **Analysis status / attempt tracking** | ❌ Missing | Add `Claim.ai_analysis_status ∈ {PENDING,RUNNING,COMPLETED,FAILED,SKIPPED}` + `ai_analysis_requested_at`, `ai_analysis_completed_at`, `ai_analysis_error` on `claims` **or** a new `ai_analyses` table. Without it, UI cannot show processing state or prevent duplicate calls. |
| **Model/provider** | ❌ Missing | Add `ClaimDecisions` or `ClaimAnalysis` column `model`/`provider` (e.g., `rocketride:gpt-4` or `mock`). Needed for cost/debug. |
| **Analysis timestamp** | Partial | `ClaimAnalysis.created_at` exists per stage; need overall `analyzed_at` on `claims` or `claim_decisions.created_at`. |
| **Extracted facts** | Partial | `ClaimAnalysis.result JSONB` per stage can store `DOCUMENT_EXTRACTION` facts (`invoice_present`, `purchase_date`, `serial_extracted`). Recommend formal Pydantic schema for `extracted_facts` but keep storage as JSONB. |
| **Warranty analysis (AI view)** | Partial | `stage="POLICY_CHECK"` row exists; but deterministic `WarrantyResult` (`warranty_eligible`, `eligibility_reason`) is already on `claims` and is authoritative. AI warranty analysis must be stored separately and never overwrite `claims.warranty_eligible`. |
| **Evidence analysis** | Partial | `stage="EVIDENCE_ANALYSIS"` row can store `evidence_consistency`, `contradictions`, `quality`. Not yet defined. |
| **Similar cases** | Weak | `HistoricalCase` table exists but is empty (no seed). `ClaimPipelineResult.similar_case_count` is scalar. For Part 2, either (a) PostgreSQL `ILIKE`/`pg_trgm` text search over `claims.fault_description` + `historical_cases.summary`, or (b) defer to separate table. **Do not add pgvector unless justified.** |
| **Recommendation + Confidence + Reasoning** | ✅ Present | `ClaimDecision.recommendation`, `confidence`, `evidence` (supporting), `risk_flags`, `missing_information` already store structured decision. `confidence` is `NUMERIC(5,2)` → validate `[0,1]`. |
| **Validator result** | Partial | `ClaimDecision.requires_human_review`, `review_reason`, `final_outcome` cover escalation, but no explicit `validation_status ∈ VALID|INVALID|REQUIRES_HUMAN_REVIEW` column. Recommend adding `validation_status` + `validation_errors JSONB`. |
| **Risk flags** | Partial/Duplicate | `RiskFlag` normalized table **and** `ClaimDecision.risk_flags TEXT[]` array both exist. Choose one owner: **Keep `ClaimDecision.risk_flags` for AI-produced flags, `RiskFlag` for persisted rule-based signals** (or deprecate array). Avoid duplicate writes. |
| **Human review linkage** | ✅ Present | `ClaimReview.claim_id → admins.id` + `ClaimDecision.final_outcome` supports `AI recommends → Validator → Human Review → Final Decision`. Need to add `claim_reviews.claim_decision_id FK` to link review to specific AI run. |
| **File references for AI** | ✅ Present | `ClaimEvidence.file_path` + `storage.py` gives relative path. Need to ensure AI never receives absolute path or unrelated claims (see §11). |

**Conclusion:** Do not duplicate `Claim/ClaimEvidence/ClaimTimeline`. **Reuse** `ClaimAnalysis` per stage + `ClaimDecision` for recommendation. **Add** minimal columns: `claims.ai_analysis_status/timestamps/error`, `claim_decisions.model/validation_status`, `claim_reviews.claim_decision_id`.

---

## 5. Recommended AI Data Model

### 5.1 Decision: Hybrid (A) + (C) — Simplest robust for hackathon

**Option A (one `ClaimAnalysis` JSON row)**: Store entire `ClaimPipelineResult` as one JSON blob. Simple but loses stage queryability (`SELECT * FROM claim_analysis WHERE stage='DOCUMENT_EXTRACTION'` not possible for the PPT stage-by-stage view).

**Option B (fully normalized tables)**: `document_extractions`, `evidence_analyses`, `similar_cases` etc. — over-engineered for hackathon, migration heavy.

**Recommended C (hybrid) — keep current `ClaimAnalysis` per stage + `ClaimDecision` as decision:**

```
claims
  ai_analysis_status: VARCHAR(30) DEFAULT 'PENDING'  -- PENDING|RUNNING|COMPLETED|FAILED|SKIPPED
  ai_analysis_requested_at: TIMESTAMPTZ
  ai_analysis_completed_at: TIMESTAMPTZ
  ai_analysis_error: TEXT  (last failure, nullable)

claim_analysis  (existing, one row per STAGE per claim)
  id SERIAL PK
  claim_id FK → claims.id  (indexed)
  stage VARCHAR(50)  -- CHECK IN STAGES
  result JSONB       -- stage-specific structured output (validated by Pydantic)
  created_at TIMESTAMPTZ

claim_decisions  (existing, one row per AI run, append-only)
  id SERIAL PK
  claim_id FK → claims.id
  model VARCHAR(100)  -- NEW: e.g., 'rocketride:mock', 'rocketride:gpt-4o'
  recommendation VARCHAR(30) CHECK IN (REPAIR,REPLACE,REFUND,DENY,MORE_INFORMATION_REQUIRED,HUMAN_REVIEW)
  confidence NUMERIC(5,2) CHECK (0<=confidence<=1)
  evidence TEXT[]        -- supporting evidence strings from AI
  risk_flags TEXT[]       -- from AI (light; detailed flags in risk_flags table)
  missing_information TEXT[]
  requires_human_review BOOLEAN
  review_reason VARCHAR(255)
  validation_status VARCHAR(30)  -- NEW: VALID|INVALID|REQUIRES_HUMAN_REVIEW (from validator)
  validation_errors JSONB         -- NEW: list of validator failures
  final_outcome VARCHAR(30)       -- NULL until human or validator finalizes (REPAIR.../DENY)
  created_at TIMESTAMPTZ

claim_decisions  ←1─N─  claim_reviews (add FK)
  claim_reviews.claim_decision_id INTEGER FK → claim_decisions.id (NEW, nullable)

risk_flags  (existing normalized)
  claim_id FK → claims.id
  flag_type VARCHAR(100)  -- e.g., 'FREQUENT_CLAIMER', 'EVIDENCE_MISMATCH'
  detail TEXT
  weight INTEGER
  created_at TIMESTAMPTZ
```

**Why hybrid:** Stage-level `claim_analysis` rows give the PPT-demanded full audit trail per stage (Evidence Extraction → Validator) without inventing 6 new tables. `claim_decisions` as append-only per run supports re-analysis (e.g., after new evidence) and links to `claim_reviews`. `claims.ai_analysis_status` drives UI `processing` spinner and prevents duplicate RocketRide calls (see §14).

**DDL sketch (additive, non-breaking):**

```sql
ALTER TABLE claims ADD COLUMN IF NOT EXISTS ai_analysis_status VARCHAR(30) DEFAULT 'PENDING';
ALTER TABLE claims ADD COLUMN IF NOT EXISTS ai_analysis_requested_at TIMESTAMPTZ;
ALTER TABLE claims ADD COLUMN IF NOT EXISTS ai_analysis_completed_at TIMESTAMPTZ;
ALTER TABLE claims ADD COLUMN IF NOT EXISTS ai_analysis_error TEXT;
ALTER TABLE claim_decisions ADD COLUMN IF NOT EXISTS model VARCHAR(100);
ALTER TABLE claim_decisions ADD COLUMN IF NOT EXISTS validation_status VARCHAR(30);
ALTER TABLE claim_decisions ADD COLUMN IF NOT EXISTS validation_errors JSONB;
ALTER TABLE claim_reviews ADD COLUMN IF NOT EXISTS claim_decision_id INTEGER REFERENCES claim_decisions(id);
CREATE INDEX IF NOT EXISTS idx_claim_analysis_claim_stage ON claim_analysis(claim_id, stage);
```

No changes to `ClaimEvidence`/`ClaimTimeline` needed; `HistoricalCase` can be seeded later for similar-case demos.

---

## 6. AI Pipeline Architecture (6 Stages + Validator + Human)

### Stage 0 — Claim Input (deterministic, pre-AI)

**Input:** `Claim.fault_description`, `fault_category`, `purchase_date` snapshot, `Product.name/category`, `WarrantyPolicy.covered/not_covered`, `ClaimEvidence` list (invoice/photo/video booleans + file bytes when needed), `customer_claim_count_90d` (count from `claims` where `customer_id` in last 90d).

**Output:** `ClaimPipelineInput` dataclass (already defined). This is the **only** object sent to `RocketRideClient`. Never send `users.email`, `JWT`, `file_path` absolute, or unrelated claims.

### Stage 1 — Evidence Extraction

**Goal:** Structured facts.

**Vendor prompt (if RocketRide is LLM):** `You are given fault_description, product_name, and evidence metadata (not raw bytes unless multimodal). Extract: {purchase_date, product_identity, serial_number, visible_damage, issue_summary, evidence_quality ∈ {low,medium,high}, extracted_text}`. **Do not hallucinate serial if not in text.** If `has_invoice=false`, return `missing_information: ["Invoice not provided"]`.

**Storage:** `claim_analysis(stage="DOCUMENT_EXTRACTION", result={invoice_present, extraction_confidence, extracted_facts})`.

### Stage 2 — Warranty Analysis (AI view, not authoritative)

**Goal:** AI’s interpretation of warranty, for comparison with deterministic engine.

**Input:** Stage 1 facts + `WarrantyPolicy`, `WarrantyResult` from `warranty_rules.py` (passed as context, not as ground truth to be overridden).

**Vendor output:** `{warranty_likely_active: bool, likely_excluded_cause: bool, policy_match_reason: string}`. **Never allow AI to set `claims.warranty_eligible`** — that column is written only by `WarrantyRuleEngine`.

**Storage:** `claim_analysis(stage="POLICY_CHECK", result={warranty_months, likely_excluded_cause, policy_check_summary})`.

### Stage 3 — Evidence Analysis

**Goal:** Consistency, completeness, quality.

**Vendor output:** `{photo_present, video_present, fault_keywords: string[], evidence_consistency: string, contradictions: string[], missing_evidence: string[], evidence_quality: float}`. Use careful language (`risk_indicator`, not `fraud`).

**Storage:** `claim_analysis(stage="EVIDENCE_ANALYSIS", result={...})`.

### Stage 4 — Similar Case Retrieval

**Goal:** Retrieve `3-5` historical claims for context.

**Recommended for hackathon (reliability > vector novelty):** PostgreSQL `pg_trgm` or `ILIKE` over `claims.fault_description` + `historical_cases.summary` filtered by `product_id` or `fault_category`. **Do not add `pgvector` unless organizer confirms embeddings are available.** `similar_case_count` scalar is stored in `ClaimPipelineResult`; optionally store `similar_case_ids: int[]`.

**Storage:** `claim_analysis(stage="SIMILAR_CASE_SEARCH", result={similar_case_count, similar_case_ids})`.

### Stage 5 — Decision Recommendation (AI only, not final)

**Goal:** Structured recommendation.

**Vendor output schema (validated by Pydantic before persist):**

```json
{
  "recommendation": "REPAIR|REPLACE|REFUND|DENY|MORE_INFORMATION_REQUIRED|HUMAN_REVIEW",
  "confidence": 0.0-1.0,
  "reasoning": ["..."],
  "supporting_evidence": ["..."],
  "contradictions": ["..."],
  "risk_flags": ["..."]
}
```

**Storage:** `claim_analysis(stage="DECISION_AGENT", result={recommendation, confidence, reasoning})` + `ClaimDecision` row (`recommendation`, `confidence`, `evidence=reasoning`, `risk_flags`, `missing_information`).

### Stage 6 — Validator (deterministic, post-AI)

**Goal:** Gate before business action.

**Checks (deterministic, no LLM):**

1. Required fields exist (`recommendation`, `confidence`).
2. `recommendation ∈ VALID_RECOMMENDATIONS`.
3. `0 ≤ confidence ≤ 1`.
4. Every `supporting_evidence` string references an existing `ClaimEvidence.id` or is `N/A` (if none, flag).
5. If AI `recommendation != MORE_INFORMATION_REQUIRED` but `WarrantyResult.eligible == false` and AI `recommendation` is `REPAIR/REPLACE` without escalation, mark `REQUIRES_HUMAN_REVIEW` (AI must not override deterministic `EXPIRED/EXCLUDED` without human).
6. If `missing_information` non-empty or `evidence` empty, require human if confidence < 0.7.
7. `risk_flags` non-empty → `REQUIRES_HUMAN_REVIEW`.
8. Schema conformance (`result` contains `recommendation` etc.).
9. No unsupported claim (e.g., AI invents `serial_number` not in input) — compare `extracted_facts.serial_number` vs `ClaimSerial.serial_number`.

**Output:** `ClaimDecision.validation_status ∈ {VALID, INVALID, REQUIRES_HUMAN_REVIEW}`, `validation_errors: [{field, error}]`, `ClaimAnalysis(stage="VALIDATOR", result={risk_flags, missing_information, validation_status, errors})`.

**Storage:** `ClaimDecision` + `claim_analysis` validator row.

### Stage 7 — Human Review (existing)

`ClaimReview` (`action ∈ APPROVE|REJECT|REQUEST_MORE_INFO|ESCALATE`) linked via `claim_decision_id`. UI shows `ClaimDecision` + validator + risk + evidence, human sets `final_outcome`. `ClaimTimeline(event_type="CLAIM_REVIEWED")` + `ClaimTimeline(event_type="DECISION_MADE")` + `audit_logs`.

---

## 7. Human Review Architecture

```
POST /api/claims (customer) → SUBMITTED
  → async ai_service.analyze(claim_id) → ClaimAnalysis ×6 + ClaimDecision (requires_human_review?)
  → Validator → validation_status
      ├─ VALID & confidence≥0.8 & no risk & warranty_eligible==true → ClaimDecision.final_outcome = recommendation (but still require admin approve per product principle for demo? Prefer always human for DENY|high-value)
      ├─ REQUIRES_HUMAN_REVIEW (default safe) → claim.status = UNDER_REVIEW, ClaimTimeline(STATUS_CHANGED), Admin queue surfaces
      └─ INVALID → claim.status = MORE_INFORMATION_REQUIRED, timeline, no auto-approve
  → Admin opens /admin/claims/{id} → sees Deterministic Warranty (authoritative) vs AI Recommendation (advisory) side-by-side, with confidence, evidence, similar cases, risk flags, validator result
  → Admin POST /api/admin/claims/{id}/review {action, notes, claim_decision_id} → ClaimReview row, ClaimDecision.final_outcome set, claim.status → APPROVED|REJECTED, timeline
  → Final action → repair_orders / replacement_orders / notifications (Phase 1.3 already has tables, Part 2 will wire)
```

**Principle enforced:** No `ClaimDecision.final_outcome` is written by AI; only `ClaimReviews` (human) or `Validator` (deterministic) can set it, and only after `requires_human_review` check. High-risk/uncertain never auto-proceeds even if AI confidence is 0.99.

---

## 8. Risk Intelligence Architecture (Defer, Design Only)

**Do not build a fraud detector labeling customers fraudulent.** Produce `risk_signal + reason + evidence + severity`.

**Signals (rule-based first, AI-assisted later):**

| Signal | Source | Storage |
|--------|--------|---------|
| `FREQUENT_CLAIMER` | `COUNT(claims) WHERE customer_id AND created_at > now-90d ≥3` | `RiskFlag(flag_type, detail="3 claims in 90 days", weight=30)` |
| `EVIDENCE_INCONSISTENCY` | `EvidenceAnalysis` contradictions | `RiskFlag` |
| `SERIAL_MISMATCH` | `WarrantyRuleEngine` ownership check | `RiskFlag` |
| `SUSPICIOUS_TIMING` | `purchase_date` near `created_at` < 7d | `RiskFlag` |
| `REPEATED_FAULT_PATTERN` | `FaultEvent` aggregation per `product_id+batch_id` | `FaultEvent` + `HistoricalCase` |
| `LOW_CONFIDENCE` | `ClaimDecision.confidence < 0.6` | `RiskFlag` |

**Language:** `risk_indicator`, `requires_review`, never `fraud`. Weights `0-100`, summed, threshold ≥50 → `REQUIRES_HUMAN_REVIEW`.

**Part 2 implementation order:** Start with deterministic `warranty_rules` + `customer_claim_count_90d` (already in `MockRocketRideClient`), then AI-derived flags from `EVIDENCE_ANALYSIS`, finally aggregate `FaultEvent`.

---

## 9. Failure Handling (AI must never destroy deterministic flow)

| Failure | Handling | Claim Status | Timeline |
|---------|----------|--------------|----------|
| RocketRide unavailable / timeout (e.g., 5s) | Catch `requests.Timeout`, set `claims.ai_analysis_status=FAILED`, `ai_analysis_error="timeout"`, no retry in request path | Remains `SUBMITTED` or `PROCESSING` | `CLAIM_TIMELINE(WARRANTY_CHECKED)` exists, `AI_ANALYSIS_FAILED` event, admin sees “AI unavailable — manual review” |
| 429 Rate limited | Exponential backoff 1s/2s/4s, max 1 retry, then `FAILED` | Same as above | Same |
| Invalid JSON / incomplete output | Pydantic `ValidationError` → `validation_status=INVALID`, `validation_errors=[...]`, log to `ai_analysis_error` | `MORE_INFORMATION_REQUIRED` if missing, else `UNDER_REVIEW` | `VALIDATOR` stage stores errors |
| Contradictory output (e.g., `recommendation=REPAIR` but `exclusions` contains policy exclusion) | Validator catches rule 5 → `REQUIRES_HUMAN_REVIEW`, `review_reason="AI contradicts deterministic warranty"` | `UNDER_REVIEW` | `VALIDATOR` + `RiskFlag` |
| No evidence provided | `Mock` returns `missing_information: ["Invoice not provided"]`; real should do same; validator requires human if `has_invoice=false` and confidence<0.7 | `MORE_INFORMATION_REQUIRED` | |

**Invariant:** `POST /api/claims` always succeeds deterministically (writes `Claim` + `WarrantyResult` + timeline) even if AI later fails. AI is **async after** creation, never blocking `201`.

---

## 10. Asynchronous Processing (Recommended)

### A) Synchronous (AI during `POST /api/claims`)

- **Pros:** Simple, immediate result for demo.
- **Cons:** Blocks `201` on vendor latency (500ms-5s), risks timeout in hackathon demo, couples claim creation to vendor availability, retries are hard.

### B) Asynchronous (AI after `POST /api/claims`) — **RECOMMENDED**

**Flow:**

1. `POST /api/claims` → `201` immediately (deterministic only), `claims.ai_analysis_status=PENDING`, `ClaimTimeline(CLAIM_CREATED, WARRANTY_CHECKED)`.
2. Background task: `ai_service.analyze_claim(claim_id)` — either `BackgroundTasks` (FastAPI) for hackathon simplicity, or `Celery/RQ` if available (not required). For MVP, use `FastAPI BackgroundTasks` + `asyncio` with `timeout=10s`.
3. Task reads `Claim` + `ClaimEvidence` + `Product/Policy`, builds `ClaimPipelineInput`, calls `RocketRideClient.run_pipeline`, writes `ClaimAnalysis ×6` + `ClaimDecision` (with `model`, `validation_status`), updates `claims.ai_analysis_status=COMPLETED|FAILED`, writes `ClaimTimeline(AI_ANALYSIS_COMPLETED|FAILED)`, optionally `claim.status=UNDER_REVIEW` if review required.
4. UI polls `GET /api/claims/{id}` (or `GET /api/claims/{id}/analysis`) every 3s while `ai_analysis_status ∈ PENDING|RUNNING`; shows `Warranty Eligibility` immediately, `AI Analysis — Running` spinner, then `AI Recommendation` when done.

**Why B:** Demo reliability (claim always created), latency hidden, rate-limit friendly (one call per claim, queued), failure recovery (retry button `POST /api/claims/{id}/analyze`), user experience (customer sees `SUBMITTED` instantly, admin sees `AI Analysis` appear).

**Claim must be created independently from AI execution** — satisfied.

---

## 11. API Design (Part 2)

### Customer APIs (read-only AI results)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/claims` | `customer` | **Existing** deterministic create (no AI) |
| `GET` | `/api/claims` | `customer` (own) | Existing |
| `GET` | `/api/claims/{id}` | `customer` (IDOR) | Existing + include `ai_analysis_status`, `ai_recommendation` (if completed) |
| `GET` | `/api/claims/{id}/analysis` | `customer` | **New:** Returns latest `ClaimDecision` (recommendation/confidence/reasoning) + `validation_status` (read-only). 403 if not own. |
| `GET` | `/api/claims/{id}/timeline` | `customer` | Existing (will include `AI_ANALYSIS_COMPLETED`) |
| `POST` | `/api/claims/{id}/analyze` | `customer` (own) | **New (idempotent):** Trigger/retry AI analysis (owner only, once per claim unless new evidence). Returns `202 Accepted` with `ai_analysis_status=PENDING`. Customer can trigger once; admin can trigger always. |

### Admin APIs

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/admin/claims` | `admin, support` | Existing queue |
| `GET` | `/api/admin/claims/{id}` | `admin, support` | Existing + include AI decision + validator + risk flags |
| `GET` | `/api/admin/claims/{id}/analysis` | `admin, support` | **New:** Detailed `ClaimAnalysis` rows (6 stages) + `ClaimDecision` + `RiskFlag` list |
| `GET` | `/api/admin/claims/{id}/risk` | `admin, support` | **New (optional):** Aggregated `RiskFlag` + `FaultEvent` for this claim/product/batch |
| `POST` | `/api/admin/claims/{id}/analyze` | `admin, support` | **New:** Force re-analysis (e.g., after new evidence) → 202 |
| `POST` | `/api/admin/claims/{id}/review` | `admin, support` | **New (human review):** `{action: APPROVE|REJECT|REQUEST_MORE_INFO|ESCALATE, notes, claim_decision_id}` → writes `ClaimReview`, sets `ClaimDecision.final_outcome`, transitions `Claim.status` via `status_machine.py`, writes `ClaimTimeline` |
| `POST` | `/api/admin/claims/{id}/decision` | `admin, support` | **Alias for review** (spec mentions this path) — map to same handler |

### Internal Service Calls (not exposed)

- `ai_service.analyze_claim(claim_id: int) -> ClaimDecision` — called by `BackgroundTasks` or `POST .../analyze` handler. Reads `Claim` + `Product` + `WarrantyPolicy` + `ClaimEvidence` + `customer_claim_count_90d`, builds `ClaimPipelineInput`, calls `RocketRideClient.run_pipeline`, validates via `validator.py`, writes `ClaimAnalysis`/`ClaimDecision`/`RiskFlag`/`ClaimTimeline`, updates `claims.ai_analysis_status`.

**All customer `GET /admin/*` remain 403 for customers (existing `require_role`).**

---

## 12. Frontend Integration Points

### Customer

| Screen | Current (Part 1.3) | Part 2 Addition |
|--------|-------------------|-----------------|
| `CustomerDashboard` (`/customer/dashboard`) | `My Products`, `My Claims`, `Requiring Attention`, `Recently Updated` | Add `AI Analysis Running` badge if any claim `ai_analysis_status=RUNNING` |
| `NewClaim` (`/customer/claims/new`) | 4-step wizard → `Warranty Claim Submitted` with `eligible/reason` | After submit, poll `GET /api/claims/{id}` for `ai_analysis_status`; show “Analysis pending — you’ll be notified when complete” (no AI detail for customer) |
| `CustomerClaims` (`/customer/claims`) | List with `StatusBadge` | Add subtle `AI: Analyzing…` chip if `ai_analysis_status=RUNNING` |
| `CustomerClaimDetail` (`/customer/claims/:id`) | `WarrantyCard` (deterministic), `EvidenceList`, `Timeline`, `StatusStepper` | Add **read-only** `AI Recommendation` section **below** `WarrantyCard` (never above): `{recommendation, confidence, reasoning}` if `analysis` exists, with fallback `AI Analysis — Running` spinner or `AI unavailable — manual review pending`. Keep label `Warranty Eligibility` deterministic, separate `AI Recommendation` advisory. |

### Admin

| Screen | Current | Part 2 Addition |
|--------|---------|-----------------|
| `AdminDashboard` (`/admin/dashboard`) | 7 status cards + quick stats | Add `AI Analyses Running/Failed` counts (from `claims.ai_analysis_status`) |
| `AdminClaims` (`/admin/claims`) | Queue with `status/product/customer/date` filters | Add column/filter `AI Status` (`PENDING|COMPLETED|FAILED`) and `Requires Human Review` badge from `ClaimDecision.requires_human_review` |
| `AdminClaimDetail` (`/admin/claims/:id`) | `Customer, Product, Warranty, Claim, Evidence, Timeline, Status Control` | **New sections (information-dense):** `AI Recommendation` (`recommendation`, `confidence` bar, `supporting_evidence`, `contradictions`), `Evidence Analysis` (from `EVIDENCE_ANALYSIS` stage), `Similar Cases` (from `SIMILAR_CASE_SEARCH` — show `similar_case_count` + list if available), `Risk Flags` (from `RiskFlag` + `Decision.risk_flags` with weight), `Validator Result` (`VALID|REQUIRES_HUMAN_REVIEW` + `validation_errors`), `Human Review` form (`Approve/Reject/Request Info` with notes, writes `ClaimReview`), `Final Decision` (`final_outcome`). Do not show `AI Analysis — Coming in Intelligence Layer` once real data exists; replace placeholder in `WarrantyCard.tsx:38` with real component. |

**Do not create fake UI data.** All admin AI sections render only if `GET /api/admin/claims/{id}/analysis` returns a decision; otherwise show `AI Analysis — Not yet run` with `Run Analysis` button (admin only).

---

## 13. Security (AI-specific)

| Concern | Requirement |
|---------|-------------|
| **Minimize PII to vendor** | Send only `ClaimPipelineInput` fields: `claim_code, product_name, category, serial_number, fault_description, purchase_date, warranty_months, covered/not_covered, has_invoice/photo/video, customer_claim_count_90d`. **Never send** `users.email`, `hashed_password`, `JWT`, `Customer.phone/address`, `User.full_name` (unless needed for `has_*` counts), or other customers’ claims. |
| **No credentials** | Never send `ROCKETRIDE_API_KEY` from frontend; only `backend` reads it via `config.py:41`. |
| **No filesystem paths** | Send `has_invoice` boolean + optionally file bytes (read via `storage.py`), never `file_path` absolute (`uploads/...`). If multimodal requires bytes, read file and send base64, do not expose path. |
| **No unrelated claims** | Similar-case retrieval runs **inside backend DB**, not via vendor. Vendor only sees the single claim’s input. |
| **Tenant isolation** | `customer_claim_count_90d` is aggregate count, not list of other claims. |
| **Validation** | Validate vendor JSON via Pydantic before persisting; discard unknown fields. |
| **Logging** | Log vendor calls to `audit_logs` (actor=`ai:rocketride`, action=`analyze`, entity=`claim`) but **redact** `fault_description` PII if needed (store truncated). |
| **Rate limit/auth** | Backend is the only RocketRide caller; frontend never calls vendor directly. Use `ROCKETRIDE_API_KEY` env, not hardcoded. |

---

## 14. Cost / Rate-Limit Strategy

**Goal: One analysis per claim, cached, no re-analysis unless explicit.**

- **Trigger once:** `POST /api/claims` → `ai_analysis_status=PENDING` → `BackgroundTasks` runs `analyze_claim` once. Subsequent `GET /api/claims/{id}` returns cached `ClaimDecision` (do not re-call).
- **Cache:** Store `ClaimDecision.created_at` + `ClaimAnalysis` rows; `GET /api/claims/{id}/analysis` reads cache, no vendor call.
- **Re-analysis only on:** `POST /api/claims/{id}/analyze` (customer once, admin force) or after new `POST /api/claims/{id}/evidence` (evidence changed). Check `claims.ai_analysis_status` — if `RUNNING`, return `409 Already analyzing`.
- **No polling of vendor:** Backend polls vendor once per claim (if async vendor requires polling, handle inside `ai_service` with timeout, not frontend).
- **Cost saving:** Deterministic preprocessing: `WarrantyRuleEngine` runs first; if `eligible==false` due to `EXPIRED` and `confidence` would be low, still run AI but vendor sees `warranty_months` and can short-circuit to `DENY` without expensive vision.
- **Evidence:** Only send relevant evidence (invoice + 1-2 photos), not all `OTHER` files; `has_invoice/photo/video` booleans are cheap, raw bytes only for `EVIDENCE_ANALYSIS` stage if multimodal is confirmed.
- **Batching:** No batch vendor calls for hackathon; one claim = one pipeline run (6 stages in one `run_pipeline` call as per adapter).

---

## 15. Implementation Order (Recommended Part 2 Sequence)

| Phase | Goal | Files | Risk |
|-------|------|-------|------|
| **2.1 Adapter Verification** | Confirm real SDK import, auth, `ClaimPipelineInput→Result` mapping, add `openai`/`rocketride` to `requirements.txt` if needed (currently not pinned) | `rocketrider/adapter.py` (implement `RealRocketRideClient`), `backend/app/core/config.py` (validate `ROCKETRIDE_MODE`), smoke test `Mock` vs `Real` toggle | **Blocked until organizer provides SDK/docs** |
| **2.2 Persistence** | Add `claims.ai_analysis_*`, `claim_decisions.model/validation_*`, `claim_reviews.claim_decision_id`, index | `database/schema.sql`, `models/claim.py`, `models/intelligence.py`, alembic or `create_all` for hackathon, seed `HistoricalCase` | Low |
| **2.3 Evidence Extraction** | Wire `ai_service.py` to read `ClaimEvidence` files + `fault_description`, call `RocketRideClient`, persist `DOCUMENT_EXTRACTION` stage | `services/ai_service.py`, `services/storage.py` (read bytes), `routers/claims.py` (call after create) | Medium (multimodal unknown) |
| **2.4 Warranty/Evidence Analysis** | Stages 2-3, ensure AI warranty does not overwrite deterministic `claims.warranty_eligible` | `ai_service.py`, `warranty_rules.py` (pass result as context) | Low |
| **2.5 Decision Recommendation** | Stage 5, validate `recommendation/confidence` schema, write `ClaimDecision` | `ai_service.py`, `models/claim.py`, Pydantic `DecisionRecommendation` | Low |
| **2.6 Validator** | Deterministic 9 checks, set `validation_status`, `requires_human_review` | `services/validator.py` (new), `services/status_machine.py` (integrate) | Low |
| **2.7 Risk Intelligence** | Rule-based `RiskFlag` (frequent claimer, low confidence, exclusion) + `FaultEvent` | `services/risk_engine.py` (new), `models/intelligence.py` | Low |
| **2.8 Async & Failure Handling** | `BackgroundTasks` + `claims.ai_analysis_status`, retry, `AI_ANALYSIS_FAILED` timeline, `POST .../analyze` 202 | `routers/claims.py`, `routers/admin_claims.py`, `services/ai_service.py` | Medium (timeout/429) |
| **2.9 Admin AI Review UI** | Show recommendation/confidence/evidence/similar/risk/validator, `POST .../review` → `ClaimReview` + `final_outcome` + status transition | `frontend/src/pages/AdminClaimDetail.tsx`, `api.ts` (`GET .../analysis`), `types/api.ts` (new `Analysis` types) | Low |
| **2.10 Customer Processing State UI** | Poll `ai_analysis_status`, show `Analyzing…` without exposing AI detail | `frontend/src/pages/CustomerClaimDetail.tsx`, `CustomerClaims.tsx` | Low |
| **2.11 Fault Intelligence + Analytics (stretch)** | `FaultEvent` aggregation per `product_id+batch_id`, `GET /api/analytics/fault-intelligence` | `routers/analytics.py`, `models/intelligence.py` | Low |

**Dependencies:** 2.1 blocks 2.3-2.5; 2.2 must precede 2.3; 2.5 must precede 2.6; 2.6 must precede 2.9.

---

## 16. Risks / Blockers

| Risk | Impact | Mitigation |
|------|--------|------------|
| No RocketRide SDK/docs in repo | Cannot implement `RealRocketRideClient` without guessing vendor syntax | **Must request organizer docs:** SDK install (`pip install rocketride`), import path, `ROCKETRIDE_API_KEY` format, endpoint `cloud.rocketride.ai` or not, multimodal file handling, structured JSON flag, workflow/agent availability, rate limits, error schema |
| HistoricalCase empty | Similar-case retrieval has no corpus | Seed `HistoricalCase` from `claims` (copy `fault_description`/`resolution`) or use `claims` text search as fallback; defer vector DB |
| pgvector not available | Cannot do embedding search | Use `ILIKE`/`pg_trgm` for hackathon; add `CREATE EXTENSION pg_trgm` if Postgres, fallback to `LIKE` for SQLite |
| Vendor latency in demo | `POST /api/claims` could hang | Use async `BackgroundTasks` (recommended) + polling; timeout 10s; show deterministic `WarrantyCard` immediately |
| Cost | Repeated analysis per page view | Cache per `claim_id`, `ai_analysis_status` guard, one call per claim |

---

## 17. Anything Requiring Organizer / Documentation Clarification

1. **SDK:** Is `rocketride` pip package? Version? Import (`import rocketride` or `from rocketride import ...`)? If not pip, is it REST `cloud.rocketride.ai`? Provide minimal `curl` example.
2. **Auth:** Is `ROCKETRIDE_API_KEY` Bearer, `x-api-key`, or OAuth? Any `ROCKETRIDE_WORKSPACE` or model param?
3. **Input:** Does RocketRide accept `has_invoice` boolean or raw PDF bytes? Max file size? Supported MIME for multimodal (PDF pages vs image JPEG)? Can PDFs/images be passed directly or must be OCR’d first?
4. **Output:** Is structured JSON (`response_format=json_object`) supported? Schema for `recommendation/confidence/reasoning`? Example `ClaimPipelineResult` JSON from vendor?
5. **Multimodal:** Is video (`video/mp4`) supported or should we limit to `INVOICE/PHOTO` for Part 2?
6. **Workflows/Agents:** Does RocketRide provide prebuilt `warranty_analysis` workflow/agent, or do we orchestrate 6 stages client-side via 6 prompts?
7. **Models:** Which model(s) to use? Is tool calling available for structured output?
8. **File input:** How to send evidence files—base64, multipart, or URL? Limit on files per call?
9. **Rate limits:** Requests per minute per API key? Concurrency? Timeout to set for `run_pipeline`?
10. **Error schema:** What JSON does vendor return on 429/500/validation failure? Can we get `error.code`?
11. **Cost:** Is each stage a separate billable call or one pipeline call? Should we batch 6 stages into one vendor call (as `Mock` does) or 6 calls?
12. **Historical case retrieval:** Is there a vendor-hosted vector store or should we use local `HistoricalCase` + Postgres search?

**Until these are clarified, do not replace `MockRocketRideClient`, do not hardcode vendor URLs, do not invent `cloud.rocketride.ai` syntax.**

---

*Audit completed without modifying `backend/` business logic or `frontend/` UI beyond documenting integration points. `WarrantyRuleEngine` remains authoritative; AI remains advisory until validator + human review.*

