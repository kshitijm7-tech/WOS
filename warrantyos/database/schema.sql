-- =========================================================
-- WarrantyOS — PostgreSQL schema (Phase 1.2)
-- Applied automatically by backend/app/core/database.py on
-- startup (create_all) for hackathon simplicity; a real
-- migration tool (Alembic) can replace this from Phase 2 on.
-- Part 1.2: Core Warranty Data + Claim Workflow
-- =========================================================

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(30) UNIQUE NOT NULL   -- 'customer' | 'admin' | 'support'
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role_id INTEGER NOT NULL REFERENCES roles(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id),
    phone VARCHAR(30),
    address TEXT
);

CREATE TABLE IF NOT EXISTS admins (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id),
    department VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS retailers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    region VARCHAR(100),
    trust_score NUMERIC(4,1) DEFAULT 100.0
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    sku VARCHAR(100) UNIQUE NOT NULL,
    category VARCHAR(100) NOT NULL,
    manufacturer VARCHAR(255),
    warranty_period_months INTEGER NOT NULL DEFAULT 12,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS production_batches (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    batch_code VARCHAR(100) NOT NULL,
    produced_on DATE,
    units_produced INTEGER DEFAULT 0,
    UNIQUE(product_id, batch_code)
);

CREATE TABLE IF NOT EXISTS product_serials (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    batch_id INTEGER REFERENCES production_batches(id),
    serial_number VARCHAR(100) UNIQUE NOT NULL,
    sold_by_retailer_id INTEGER REFERENCES retailers(id),
    purchase_date DATE,
    owner_customer_id INTEGER REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS warranty_policies (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    warranty_months INTEGER NOT NULL,
    covered TEXT[],           -- e.g. {"Manufacturing defects","Motor failure"}
    not_covered TEXT[],       -- e.g. {"Accidental damage","Water damage"}
    conditions TEXT,          -- human-readable conditions
    covered_fault_categories TEXT[],
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS claims (
    id SERIAL PRIMARY KEY,
    claim_code VARCHAR(20) UNIQUE NOT NULL,     -- e.g. WR-10482
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    serial_id INTEGER REFERENCES product_serials(id),
    retailer_id INTEGER REFERENCES retailers(id),
    fault_description TEXT NOT NULL,
    fault_category VARCHAR(100),
    status VARCHAR(40) NOT NULL DEFAULT 'SUBMITTED', -- SUBMITTED|PROCESSING|UNDER_REVIEW|APPROVED|REJECTED|MORE_INFORMATION_REQUIRED|RESOLVED
    purchase_date DATE,                        -- snapshot from ProductSerial at creation
    warranty_eligible BOOLEAN,
    eligibility_reason TEXT,
    warranty_checked_at TIMESTAMP,
    exclusions_triggered TEXT[],
    missing_information TEXT[],
    final_decision VARCHAR(30),                 -- REPAIR | REPLACE | REFUND | DENY
    confidence NUMERIC(5,2),
    is_high_value BOOLEAN DEFAULT FALSE,
    -- Part 2.1: AI analysis lifecycle (offline Mock)
    ai_analysis_status VARCHAR(30) DEFAULT 'PENDING', -- PENDING|RUNNING|COMPLETED|FAILED|SKIPPED
    ai_analysis_requested_at TIMESTAMP,
    ai_analysis_completed_at TIMESTAMP,
    ai_analysis_error TEXT,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS claim_evidence (
    id SERIAL PRIMARY KEY,
    claim_id INTEGER NOT NULL REFERENCES claims(id),
    evidence_type VARCHAR(30) NOT NULL,   -- INVOICE | PHOTO | VIDEO | OTHER
    file_path VARCHAR(500) NOT NULL,
    original_filename VARCHAR(255),
    stored_filename VARCHAR(255),
    mime_type VARCHAR(100),
    file_size INTEGER,
    uploaded_by_user_id INTEGER REFERENCES users(id),
    description TEXT,
    uploaded_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS claim_analysis (
    id SERIAL PRIMARY KEY,
    claim_id INTEGER NOT NULL REFERENCES claims(id),
    stage VARCHAR(50) NOT NULL,   -- matches rocketrider pipeline stage names
    result JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS claim_decisions (
    id SERIAL PRIMARY KEY,
    claim_id INTEGER NOT NULL REFERENCES claims(id),
    recommendation VARCHAR(30) NOT NULL,
    confidence NUMERIC(5,2) NOT NULL,
    evidence TEXT[],
    risk_flags TEXT[],
    missing_information TEXT[],
    requires_human_review BOOLEAN DEFAULT FALSE,
    review_reason VARCHAR(255),
    final_outcome VARCHAR(30),   -- set only after validation / human review
    -- Part 2.1: AI persistence
    model VARCHAR(100),
    validation_status VARCHAR(30), -- VALID|INVALID|REQUIRES_HUMAN_REVIEW
    validation_errors JSONB,
    -- Part 2.3: Governance
    decision_version INTEGER DEFAULT 1,
    decision_score NUMERIC(5,2),
    confidence_band VARCHAR(20), -- HIGH|MEDIUM|LOW
    conflicts JSONB,
    explanation JSONB,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS claim_reviews (
    id SERIAL PRIMARY KEY,
    claim_id INTEGER NOT NULL REFERENCES claims(id),
    reviewed_by_admin_id INTEGER REFERENCES admins(id),
    claim_decision_id INTEGER REFERENCES claim_decisions(id),
    action VARCHAR(30) NOT NULL,   -- APPROVE | REJECT | REQUEST_MORE_INFO | ESCALATE | OVERRIDE
    notes TEXT,
    status VARCHAR(30) DEFAULT 'PENDING', -- PENDING|IN_PROGRESS|COMPLETED|REQUESTED_INFORMATION|OVERRIDDEN
    human_decision VARCHAR(30),
    override BOOLEAN DEFAULT FALSE,
    override_reason TEXT,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS claim_timeline (
    id SERIAL PRIMARY KEY,
    claim_id INTEGER NOT NULL REFERENCES claims(id),
    event_type VARCHAR(100) NOT NULL, -- CLAIM_CREATED | EVIDENCE_UPLOADED | WARRANTY_CHECKED | STATUS_CHANGED | INFORMATION_REQUESTED | DECISION_MADE | ADMIN_ACTION | AI_ANALYSIS_STARTED | AI_ANALYSIS_COMPLETED | AI_ANALYSIS_FAILED | AI_VALIDATION_FAILED | AI_HUMAN_REVIEW_REQUIRED
    actor VARCHAR(100),          -- 'system' | 'customer' | 'admin:<name>' | 'ai'
    notes TEXT,
    event_metadata JSONB,
    created_at TIMESTAMP DEFAULT now()
);

-- Part 2.1: index for per-claim stage lookup
CREATE INDEX IF NOT EXISTS idx_claim_analysis_claim_stage ON claim_analysis(claim_id, stage);

-- Part 2.4: AI Execution history (lightweight, provider-agnostic)
CREATE TABLE IF NOT EXISTS ai_executions (
    id SERIAL PRIMARY KEY,
    execution_id VARCHAR(64) UNIQUE NOT NULL,
    claim_id INTEGER NOT NULL REFERENCES claims(id),
    status VARCHAR(30) NOT NULL, -- QUEUED|RUNNING|VALIDATING|GOVERNING|COMPLETED|FAILED|CANCELLED|TIMED_OUT
    provider VARCHAR(50) NOT NULL DEFAULT 'mock',
    model VARCHAR(100) NOT NULL DEFAULT 'mock-v1',
    pipeline_version VARCHAR(20) NOT NULL DEFAULT '2.4',
    attempt INTEGER NOT NULL DEFAULT 1,
    requested_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,
    error_code VARCHAR(50),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ai_executions_claim_status ON ai_executions(claim_id, status);
CREATE INDEX IF NOT EXISTS idx_ai_executions_execution_id ON ai_executions(execution_id);

CREATE TABLE IF NOT EXISTS repair_orders (
    id SERIAL PRIMARY KEY,
    claim_id INTEGER UNIQUE NOT NULL REFERENCES claims(id),
    scheduled_date DATE,
    technician VARCHAR(255),
    status VARCHAR(30) DEFAULT 'SCHEDULED'
);

CREATE TABLE IF NOT EXISTS inventory (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    warehouse VARCHAR(100) NOT NULL,
    available_qty INTEGER DEFAULT 0,
    reserved_qty INTEGER DEFAULT 0,
    reorder_threshold INTEGER DEFAULT 10
);

CREATE TABLE IF NOT EXISTS replacement_orders (
    id SERIAL PRIMARY KEY,
    claim_id INTEGER UNIQUE NOT NULL REFERENCES claims(id),
    inventory_id INTEGER REFERENCES inventory(id),
    status VARCHAR(30) DEFAULT 'PROCESSING'
);

CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS historical_cases (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    fault_category VARCHAR(100),
    resolution VARCHAR(30),
    summary TEXT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fault_events (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    batch_id INTEGER REFERENCES production_batches(id),
    component VARCHAR(100) NOT NULL,
    claim_id INTEGER REFERENCES claims(id),
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS risk_flags (
    id SERIAL PRIMARY KEY,
    claim_id INTEGER NOT NULL REFERENCES claims(id),
    flag_type VARCHAR(100) NOT NULL,
    detail TEXT,
    weight INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    actor VARCHAR(100) NOT NULL,
    action VARCHAR(255) NOT NULL,
    entity VARCHAR(100),
    entity_id INTEGER,
    created_at TIMESTAMP DEFAULT now()
);
