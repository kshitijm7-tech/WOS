export interface User {
  id: number;
  email: string;
  full_name: string;
  role: string;
}

export interface Product {
  id: number;
  name: string;
  sku: string;
  category: string;
  manufacturer?: string | null;
  warranty_period_months: number;
}

export interface ProductSerial {
  id: number;
  serial_number: string;
  product_id: number;
  product_name?: string | null;
  product_sku?: string | null;
  purchase_date?: string | null;
  retailer?: string | null;
}

export interface ProductDetail {
  id: number;
  name: string;
  sku: string;
  category: string;
  manufacturer?: string | null;
  warranty_period_months: number;
  policy?: {
    warranty_months: number;
    covered: string[];
    not_covered: string[];
    conditions?: string | null;
  } | null;
}

export interface WarrantyResult {
  eligible: boolean;
  warranty_active: boolean;
  policy_match: boolean;
  reason: string;
  exclusions_triggered: string[];
  missing_information: string[];
  purchase_date?: string | null;
  warranty_end_date?: string | null;
}

export interface Claim {
  id: number;
  claim_code: string;
  customer_id: number;
  product_id: number;
  serial_id?: number | null;
  retailer_id?: number | null;
  fault_description: string;
  fault_category?: string | null;
  status: string;
  purchase_date?: string | null;
  warranty_eligible?: boolean | null;
  eligibility_reason?: string | null;
  warranty_checked_at?: string | null;
  exclusions_triggered?: string[] | null;
  missing_information?: string[] | null;
  ai_analysis_status?: string | null;
  ai_analysis_requested_at?: string | null;
  ai_analysis_completed_at?: string | null;
  ai_analysis_error?: string | null;
  created_at: string;
  updated_at: string;
  warranty?: WarrantyResult | null;
}

export interface AIStageOutput {
  stage: string;
  result: Record<string, unknown>;
  created_at: string;
}

export interface AIDecision {
  id: number;
  claim_id: number;
  recommendation: string;
  confidence: number;
  evidence: string[];
  risk_flags: string[];
  missing_information: string[];
  requires_human_review: boolean;
  review_reason?: string | null;
  final_outcome?: string | null;
  model?: string | null;
  validation_status?: string | null;
  validation_errors?: Record<string, unknown>[] | null;
  decision_version?: number | null;
  decision_score?: number | null;
  confidence_band?: string | null;
  conflicts?: Array<{ conflict_code: string; description: string; source: string; severity: string; metadata?: Record<string, unknown> }> | null;
  explanation?: {
    summary: string;
    reasoning_factors: string[];
    supporting_evidence: string[];
    contradicting_evidence: string[];
    policy_references: string[];
    historical_case_references: string[];
    risk_factors: string[];
    confidence_explanation: string;
  } | null;
  created_at: string;
}

export interface Review {
  id: number;
  claim_id: number;
  claim_decision_id?: number | null;
  reviewed_by_admin_id?: number | null;
  action: string;
  notes?: string | null;
  status?: string | null;
  human_decision?: string | null;
  override?: boolean | null;
  override_reason?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface AIAnalysis {
  claim_id: number;
  claim_code: string;
  ai_analysis_status: string;
  ai_analysis_requested_at?: string | null;
  ai_analysis_completed_at?: string | null;
  ai_analysis_error?: string | null;
  stages: AIStageOutput[];
  decision?: AIDecision | null;
  recommendation?: string | null;
  confidence?: number | null;
  validation_status?: string | null;
  requires_human_review?: boolean | null;
}

export interface Evidence {
  id: number;
  claim_id: number;
  evidence_type: string;
  original_filename?: string | null;
  stored_filename?: string | null;
  mime_type?: string | null;
  file_size?: number | null;
  description?: string | null;
  uploaded_at: string;
}

export interface TimelineEvent {
  id: number;
  claim_id: number;
  event_type: string;
  actor?: string | null;
  notes?: string | null;
  event_metadata?: Record<string, unknown> | null;
  created_at: string;
}

export interface ClaimDetail extends Claim {
  product?: Product | null;
  serial?: {
    id: number;
    serial_number: string;
    purchase_date?: string | null;
    product_id: number;
  } | null;
  customer?: {
    id: number;
    user_id: number;
    full_name: string;
    email: string;
  } | null;
  evidence: Evidence[];
  timeline: TimelineEvent[];
}

export interface ClaimCreatePayload {
  product_id: number;
  serial_number?: string | null;
  retailer_id?: number | null;
  fault_description: string;
  fault_category?: string | null;
  purchase_date?: string | null; // YYYY-MM-DD
}
