import { useEffect, useState, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import AdminLayout from "../layouts/AdminLayout";
import { api, ApiError } from "../lib/api";
import { ClaimDetail, AIAnalysis, Review } from "../types/api";
import StatusBadge from "../components/StatusBadge";
import Timeline from "../components/Timeline";
import WarrantyCard from "../components/WarrantyCard";
import EvidenceList from "../components/EvidenceList";
import StatusStepper from "../components/StatusStepper";
import AIAnalysisCard from "../components/AIAnalysisCard";
import { Loading, ErrorState, Card, Button } from "../components/ui";

const ALL_STATUSES = ["SUBMITTED","PROCESSING","UNDER_REVIEW","APPROVED","REJECTED","MORE_INFORMATION_REQUIRED","RESOLVED"] as const;
const TRANSITIONS: Record<string, string[]> = {
  SUBMITTED: ["PROCESSING"],
  PROCESSING: ["UNDER_REVIEW","APPROVED","REJECTED","MORE_INFORMATION_REQUIRED"],
  UNDER_REVIEW: ["APPROVED","REJECTED","MORE_INFORMATION_REQUIRED"],
  APPROVED: ["RESOLVED"],
  REJECTED: [],
  MORE_INFORMATION_REQUIRED: ["PROCESSING"],
  RESOLVED: [],
};

export default function AdminClaimDetail() {
  const { id } = useParams();
  const [claim, setClaim] = useState<ClaimDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionOk, setActionOk] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<AIAnalysis | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [reviews, setReviews] = useState<Review[] | null>(null);
  const [reviewAction, setReviewAction] = useState<string>("APPROVE");
  const [reviewNotes, setReviewNotes] = useState("");
  const [overrideDecision, setOverrideDecision] = useState("REPLACE");
  const [overrideReason, setOverrideReason] = useState("");
  const [executions, setExecutions] = useState<Array<{execution_id:string;status:string;provider:string;model:string;pipeline_version:string;attempt:number;duration_ms?:number|null;requested_at?:string|null;completed_at?:string|null;error_code?:string|null;error_message?:string|null}> | null>(null);
  const pollRef = useRef<number | null>(null);

  async function load() {
    try {
      const data = await api.get<ClaimDetail>(`/admin/claims/${id}`);
      setClaim(data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed");
    }
  }
  async function loadAnalysis() {
    try {
      const data = await api.get<AIAnalysis>(`/admin/claims/${id}/analysis`);
      setAnalysis(data);
      return data;
    } catch (e) {
      setAnalysisError(e instanceof ApiError ? e.message : "Failed to load AI analysis");
      return null;
    }
  }
  async function loadReviews() {
    try {
      const data = await api.get<Review[]>(`/admin/claims/${id}/reviews`);
      setReviews(data);
    } catch {
      setReviews([]);
    }
  }
  async function loadExecutions() {
    try {
      const data = await api.get<{executions: Array<{execution_id:string;status:string;provider:string;model:string;pipeline_version:string;attempt:number;duration_ms?:number|null;requested_at?:string|null;completed_at?:string|null;error_code?:string|null;error_message?:string|null}>}>(`/admin/claims/${id}/ai-executions`);
      setExecutions(data.executions);
    } catch {
      setExecutions([]);
    }
  }
  useEffect(() => { load(); loadAnalysis(); loadReviews(); loadExecutions(); }, [id]);

  useEffect(() => {
    if (analysis?.ai_analysis_status === "RUNNING") {
      const handle = window.setInterval(async () => {
        const data = await loadAnalysis();
        if (data && data.ai_analysis_status !== "RUNNING") {
          window.clearInterval(handle);
          load();
          loadExecutions();
        }
      }, 2000);
      pollRef.current = handle;
      return () => window.clearInterval(handle);
    }
  }, [analysis?.ai_analysis_status]);

  async function handleStartAI() {
    if (!claim) return;
    setAnalysisError(null);
    try {
      await api.post(`/admin/claims/${claim.id}/analyze`, {});
      await loadAnalysis();
      await load();
      await loadExecutions();
    } catch (e) {
      setAnalysisError(e instanceof ApiError ? e.message : "Failed to start AI analysis");
    }
  }

  async function handleTransition(to: string) {
    if (!claim) return;
    setActionError(null); setActionOk(null);
    try {
      // Use customer status endpoint — it is IDOR-protected but allows admin
      await api.patch(`/claims/${claim.id}/status`, { new_status: to, notes: `Admin transition ${claim.status} → ${to}` });
      setActionOk(`Moved to ${to}`);
      await load();
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Transition failed");
    }
  }

  async function handleReview() {
    if (!claim) return;
    setActionError(null); setActionOk(null);
    try {
      const payload: Record<string, string> = { action: reviewAction, notes: reviewNotes };
      if (reviewAction === "OVERRIDE") {
        payload.decision = overrideDecision;
        payload.reason = overrideReason;
        if (!overrideReason) {
          setActionError("Override requires a reason.");
          return;
        }
      }
      await api.post(`/admin/claims/${claim.id}/review`, payload);
      setActionOk(`Review ${reviewAction} submitted`);
      setReviewNotes("");
      setOverrideReason("");
      await loadReviews();
      await load();
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Review failed");
    }
  }

  if (!claim) {
    if (error) return <AdminLayout><ErrorState message={error} onRetry={load} /></AdminLayout>;
    return <AdminLayout><Loading /></AdminLayout>;
  }

  const next = TRANSITIONS[claim.status] || [];

  return (
    <AdminLayout>
      <Link to="/admin/claims" className="text-sm text-slate-light hover:text-ink">← Claims Queue</Link>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <h1 className="font-display font-semibold text-2xl">{claim.claim_code}</h1>
        <StatusBadge status={claim.status} />
        <span className="text-xs font-mono text-slate-light">{claim.fault_category} · {new Date(claim.created_at).toLocaleDateString()}</span>
      </div>

      <div className="mt-6">
        <StatusStepper status={claim.status} />
      </div>

      <div className="grid lg:grid-cols-3 gap-6 mt-6">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <h3 className="font-semibold text-sm mb-3">Customer</h3>
            <div className="text-sm space-y-1">
              <div className="flex justify-between"><span className="text-slate-light">Name</span><span className="font-medium">{claim.customer?.full_name || "—"}</span></div>
              <div className="flex justify-between"><span className="text-slate-light">Email</span><span className="font-mono">{claim.customer?.email || "—"}</span></div>
              <div className="flex justify-between"><span className="text-slate-light">Customer ID</span><span>#{claim.customer_id}</span></div>
            </div>
          </Card>

          <Card>
            <h3 className="font-semibold text-sm mb-3">Product</h3>
            <div className="grid sm:grid-cols-2 gap-3 text-sm">
              <div><span className="text-slate-light">Product</span><p className="font-medium">{claim.product?.name || `Product #${claim.product_id}`}</p><p className="text-xs font-mono text-slate-light">{claim.product?.sku}</p></div>
              <div><span className="text-slate-light">Serial</span><p className="font-mono font-medium">{claim.serial?.serial_number || "—"}</p><p className="text-xs text-slate-light">Purchase: {claim.purchase_date || claim.serial?.purchase_date || "—"}</p></div>
            </div>
            <div className="mt-4 pt-4 border-t border-line">
              <p className="text-xs font-semibold text-slate-dark">Claim</p>
              <p className="text-sm text-ink mt-1"><span className="font-medium">{claim.fault_category}</span> — {claim.fault_description}</p>
            </div>
          </Card>

          <Card>
            <h3 className="font-semibold text-sm mb-3">Evidence</h3>
            <EvidenceList evidence={claim.evidence} />
          </Card>

          <Card>
            <h3 className="font-semibold text-sm mb-3">Timeline — Full Audit Trail</h3>
            <Timeline events={claim.timeline} />
          </Card>
        </div>

        <div className="space-y-6">
          <WarrantyCard claim={claim} />
          <AIAnalysisCard analysis={analysis} onStart={handleStartAI} />
          {analysisError && <p className="text-xs text-alert bg-alert-soft rounded px-2 py-1">{analysisError}</p>}

          <Card>
            <h3 className="font-semibold text-sm mb-3">Human Review</h3>
            <p className="text-xs text-slate-light">AI is advisory; human decides. {analysis?.decision?.requires_human_review ? "⚠ Human review required" : "No review required"}</p>
            {reviews && reviews.length > 0 && (
              <div className="mt-3 space-y-2">
                <p className="text-xs font-semibold">Recent reviews</p>
                {reviews.slice(0,3).map((r) => (
                  <div key={r.id} className="text-xs bg-paper border border-line rounded p-2">
                    <p className="font-mono">{r.action} {r.human_decision ? `→ ${r.human_decision}` : ""} {r.override ? "(override)" : ""}</p>
                    <p className="text-slate-light">{r.notes || r.override_reason || ""} · {new Date(r.created_at).toLocaleString()}</p>
                  </div>
                ))}
              </div>
            )}
            <div className="mt-3 grid gap-2">
              <select value={reviewAction} onChange={(e)=>setReviewAction(e.target.value)} className="rounded-md border border-line px-2 py-2 text-sm">
                <option value="APPROVE">APPROVE</option>
                <option value="REJECT">REJECT</option>
                <option value="REQUEST_INFORMATION">REQUEST_INFORMATION</option>
                <option value="OVERRIDE">OVERRIDE</option>
                <option value="ESCALATE">ESCALATE</option>
              </select>
              {reviewAction === "OVERRIDE" && (
                <>
                  <select value={overrideDecision} onChange={(e)=>setOverrideDecision(e.target.value)} className="rounded-md border border-line px-2 py-2 text-sm">
                    <option value="REPAIR">REPAIR</option>
                    <option value="REPLACE">REPLACE</option>
                    <option value="DENY">DENY</option>
                    <option value="HUMAN_REVIEW">HUMAN_REVIEW</option>
                  </select>
                  <input placeholder="Override reason (required)" value={overrideReason} onChange={(e)=>setOverrideReason(e.target.value)} className="rounded-md border border-line px-3 py-2 text-sm" />
                </>
              )}
              <input placeholder="Notes (optional)" value={reviewNotes} onChange={(e)=>setReviewNotes(e.target.value)} className="rounded-md border border-line px-3 py-2 text-sm" />
              <Button onClick={handleReview}>Submit Review</Button>
            </div>
            <p className="text-xs text-slate-light mt-2">Review is immutable; new analysis creates Decision v2. Override requires reason.</p>
          </Card>

          <Card>
            <h3 className="font-semibold text-sm mb-3">AI Execution History</h3>
            <p className="text-xs text-slate-light">Safe metadata only — no PII/file paths.</p>
            {!executions ? (
              <p className="text-xs text-slate-light mt-2">Loading…</p>
            ) : executions.length === 0 ? (
              <p className="text-xs text-slate-light mt-2">No executions yet. Run AI analysis to create one.</p>
            ) : (
              <div className="mt-3 space-y-2">
                {executions.map((e) => (
                  <div key={e.execution_id} className="bg-paper border border-line rounded p-2">
                    <div className="flex items-center gap-2 text-xs font-mono">
                      <span className={e.status === "COMPLETED" ? "text-teal" : e.status === "FAILED" || e.status === "TIMED_OUT" ? "text-alert" : "text-amber"}>● {e.status}</span>
                      <span className="truncate">{e.execution_id}</span>
                    </div>
                    <div className="text-xs text-slate-light mt-1">
                      Provider: {e.provider} · Model: {e.model} · Pipeline: {e.pipeline_version} · Attempt: {e.attempt} {e.duration_ms ? `· ${e.duration_ms} ms` : ""}
                    </div>
                    {e.error_code && <p className="text-xs text-alert mt-1">{e.error_code}: {e.error_message}</p>}
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card>
            <h3 className="font-semibold text-sm mb-3">Admin Status Control</h3>
            <p className="text-xs text-slate-light">Only valid next states are shown. Backend is authority.</p>
            <div className="mt-3">
              <p className="text-sm">Current: <StatusBadge status={claim.status} /></p>
              {next.length === 0 ? (
                <p className="text-sm text-slate-light mt-3">No transitions — terminal state.</p>
              ) : (
                <div className="grid gap-2 mt-3">
                  {next.map((n) => (
                    <Button key={n} onClick={() => handleTransition(n)} variant="secondary">{n.replaceAll("_"," ")}</Button>
                  ))}
                </div>
              )}
              {actionError && <p className="text-xs text-alert bg-alert-soft rounded px-2 py-1 mt-3">{actionError}</p>}
              {actionOk && <p className="text-xs text-teal bg-teal-soft rounded px-2 py-1 mt-3">{actionOk}</p>}
            </div>
            <div className="mt-4 rounded border border-dashed border-line bg-paper p-2">
              <p className="text-xs font-mono text-slate-light">Invalid transition → 409 Conflict is expected behavior.</p>
            </div>
          </Card>
        </div>
      </div>
    </AdminLayout>
  );
}
