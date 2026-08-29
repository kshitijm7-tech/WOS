import { useEffect, useState, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import CustomerLayout from "../layouts/CustomerLayout";
import { api, ApiError } from "../lib/api";
import { ClaimDetail, AIAnalysis } from "../types/api";
import StatusBadge from "../components/StatusBadge";
import Timeline from "../components/Timeline";
import WarrantyCard from "../components/WarrantyCard";
import EvidenceList from "../components/EvidenceList";
import StatusStepper from "../components/StatusStepper";
import AIAnalysisCard from "../components/AIAnalysisCard";
import { Loading, ErrorState, Card, Button } from "../components/ui";

export default function CustomerClaimDetail() {
  const { id } = useParams();
  const [claim, setClaim] = useState<ClaimDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<AIAnalysis | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  async function load() {
    try {
      const data = await api.get<ClaimDetail>(`/claims/${id}`);
      setClaim(data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed");
    }
  }
  async function loadAnalysis() {
    try {
      const data = await api.get<AIAnalysis>(`/claims/${id}/analysis`);
      setAnalysis(data);
      return data;
    } catch (e) {
      setAnalysisError(e instanceof ApiError ? e.message : "Failed to load AI analysis");
      return null;
    }
  }
  useEffect(() => { load(); loadAnalysis(); }, [id]);

  useEffect(() => {
    if (analysis?.ai_analysis_status === "RUNNING") {
      const handle = window.setInterval(async () => {
        const data = await loadAnalysis();
        if (data && data.ai_analysis_status !== "RUNNING") {
          window.clearInterval(handle);
          load(); // refresh timeline
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
      await api.post(`/claims/${claim.id}/analyze`, {});
      await loadAnalysis();
      // also refresh claim to show updated ai_analysis_status
      await load();
    } catch (e) {
      setAnalysisError(e instanceof ApiError ? e.message : "Failed to start AI analysis");
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !claim) return;
    setUploading(true);
    setUploadError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("evidence_type", file.type.startsWith("image") ? "PHOTO" : file.type === "application/pdf" ? "INVOICE" : "OTHER");
      await api.upload(`/claims/${claim.id}/evidence`, fd);
      await load();
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  async function handleReturnToProcessing() {
    if (!claim) return;
    try {
      await api.patch(`/claims/${claim.id}/status`, { new_status: "PROCESSING" });
      await load();
    } catch (e) {
      setUploadError(e instanceof ApiError ? e.message : "Status change failed");
    }
  }

  if (!claim) {
    if (error) return <CustomerLayout><ErrorState message={error} onRetry={load} /></CustomerLayout>;
    return <CustomerLayout><Loading /></CustomerLayout>;
  }

  const needsMoreInfo = claim.status === "MORE_INFORMATION_REQUIRED";

  return (
    <CustomerLayout>
      <Link to="/customer/claims" className="text-sm text-slate-light hover:text-ink">← My Claims</Link>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <h1 className="font-display font-semibold text-2xl">{claim.claim_code}</h1>
        <StatusBadge status={claim.status} />
        <span className="text-xs text-slate-light font-mono">{new Date(claim.created_at).toLocaleDateString()} · {claim.fault_category}</span>
      </div>

      {needsMoreInfo && (
        <div className="mt-4 bg-amber-soft border border-amber/20 rounded-lg p-4">
          <p className="text-sm font-semibold text-ink">Additional Information Required</p>
          <p className="text-sm text-slate mt-1">{claim.missing_information?.length ? claim.missing_information.join("; ") : claim.eligibility_reason || "Please provide additional evidence or details."}</p>
          <Button onClick={handleReturnToProcessing} className="mt-3">Return to Processing</Button>
          <p className="text-xs text-slate-light mt-2">Button triggers backend transition MORE_INFORMATION_REQUIRED → PROCESSING.</p>
        </div>
      )}

      <div className="mt-6">
        <StatusStepper status={claim.status} />
      </div>

      <div className="grid lg:grid-cols-3 gap-6 mt-6">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <h3 className="font-semibold text-sm mb-3">Claim Header</h3>
            <div className="grid sm:grid-cols-2 gap-3 text-sm">
              <div><span className="text-slate-light">Product</span><p className="font-medium">{claim.product?.name || `Product #${claim.product_id}`}</p><p className="text-xs font-mono text-slate-light">{claim.product?.sku}</p></div>
              <div><span className="text-slate-light">Serial</span><p className="font-mono font-medium">{claim.serial?.serial_number || "—"}</p><p className="text-xs text-slate-light">Purchase: {claim.purchase_date || claim.serial?.purchase_date || "—"}</p></div>
              <div className="sm:col-span-2"><span className="text-slate-light text-xs">Issue</span><p className="text-sm text-ink mt-1">{claim.fault_description}</p></div>
            </div>
          </Card>

          <Card>
            <h3 className="font-semibold text-sm mb-3">Evidence</h3>
            <EvidenceList evidence={claim.evidence} />
            <div className="mt-4">
              <label className="block">
                <span className="text-sm font-medium">Upload additional evidence</span>
                <input type="file" onChange={handleUpload} disabled={uploading || claim.status === "RESOLVED"} className="mt-1 block w-full text-sm" />
              </label>
              {uploading && <p className="text-xs text-slate mt-2">Uploading…</p>}
              {uploadError && <p className="text-xs text-alert bg-alert-soft rounded px-2 py-1 mt-2">{uploadError}</p>}
              {claim.status === "RESOLVED" && <p className="text-xs text-slate-light mt-2">Cannot upload to resolved claim.</p>}
            </div>
          </Card>

          <Card>
            <h3 className="font-semibold text-sm mb-3">Timeline — Audit Trail</h3>
            <Timeline events={claim.timeline} />
          </Card>
        </div>

        <div className="space-y-6">
          <WarrantyCard claim={claim} />
          <AIAnalysisCard analysis={analysis} onStart={handleStartAI} />
          {analysisError && <p className="text-xs text-alert bg-alert-soft rounded px-2 py-1">{analysisError}</p>}
          <Card>
            <h3 className="font-semibold text-sm mb-2">Status</h3>
            <p className="text-xs text-slate-light">Current status drives next actions. Backend is authority; UI only shows valid next states.</p>
            <div className="mt-3 text-sm">
              <span className="text-slate-light">Current:</span> <StatusBadge status={claim.status} />
            </div>
            {needsMoreInfo && <p className="text-xs text-amber mt-2">You can return to PROCESSING after providing info.</p>}
          </Card>
        </div>
      </div>
    </CustomerLayout>
  );
}
