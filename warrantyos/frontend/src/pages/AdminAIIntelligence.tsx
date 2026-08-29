import { useEffect, useState } from "react";
import AdminLayout from "../layouts/AdminLayout";
import { api, ApiError } from "../lib/api";
import { Card, Loading, ErrorState } from "../components/ui";

interface AIHealthResponse {
  status: string;
  configured_provider: string;
  active_provider: string;
  embedding_provider: string;
  vector_store: string;
  ocr_provider: string;
  fallback_enabled: boolean;
  fallback_used: boolean;
  pipeline_version: string;
}

interface EvaluationResponse {
  evaluation_sample_size: number;
  with_human_review: number;
  observed_agreement: number | null;
  human_ai_agreement: number | null;
  approval_rate: number | null;
  rejection_rate: number | null;
  override_rate: number | null;
  review_required_rate: number | null;
  avg_confidence: number | null;
  confidence_calibration?: {
    calibration_status: string;
    brier_score?: number | null;
    calibration_error?: number | null;
  };
  agreement_by_confidence_band?: Record<string, { sample_size: number; agreement: number | null }>;
  agreement_by_risk_level?: Record<string, { sample_size: number; agreement: number | null }>;
}

interface RetrievalEvaluationResponse {
  status: string;
  dataset_size: number;
  evaluated_claims?: number;
  precision_at_1?: number | null;
  precision_at_3?: number | null;
  precision_at_5?: number | null;
  mrr?: number | null;
  average_similarity?: number | null;
}

export default function AdminAIIntelligence() {
  const [health, setHealth] = useState<AIHealthResponse | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationResponse | null>(null);
  const [retrieval, setRetrieval] = useState<RetrievalEvaluationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [h, ev, r] = await Promise.all([
        api.get<AIHealthResponse>("/admin/ai/health"),
        api.get<EvaluationResponse>("/admin/evaluation"),
        api.get<RetrievalEvaluationResponse>("/admin/evaluation/retrieval"),
      ]);
      setHealth(h);
      setEvaluation(ev);
      setRetrieval(r);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load intelligence metrics");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  if (loading) {
    return (
      <AdminLayout>
        <Loading text="Loading AI Intelligence & Telemetry data..." />
      </AdminLayout>
    );
  }

  if (error || !health) {
    return (
      <AdminLayout>
        <ErrorState message={error || "Could not reach AI Diagnostics API"} onRetry={loadData} />
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display font-semibold text-2xl">AI Intelligence & Evaluation</h1>
          <p className="text-sm text-slate-light mt-1">
            Production intelligence, retrieval metrics, evaluation & execution telemetry.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-mono font-medium ${
              health.status === "healthy"
                ? "bg-teal/10 text-teal border border-teal/20"
                : "bg-alert/10 text-alert border border-alert/20"
            }`}
          >
            System Status: {health.status.toUpperCase()}
          </span>
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-white/10 text-paper">
            Offline Mode Active
          </span>
        </div>
      </div>

      {/* Provider Truthfulness Banner */}
      <div className="mb-8 p-4 rounded-xl border border-line bg-paper-light">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-mono uppercase tracking-wider text-slate-light">Provider Truthfulness</p>
            <div className="flex items-center gap-3 mt-1">
              <span className="font-semibold text-base">Configured: <code className="font-mono text-teal">{health.configured_provider}</code></span>
              <span className="text-slate-light">→</span>
              <span className="font-semibold text-base">Actual Executed: <code className="font-mono text-teal">{health.active_provider}</code></span>
            </div>
          </div>
          <div className="text-right">
            <p className="text-xs text-slate-light font-mono">Fallback Status</p>
            <p className={`text-sm font-semibold mt-0.5 ${health.fallback_used ? "text-alert" : "text-teal"}`}>
              {health.fallback_used ? "Fallback Triggered (Mock Active)" : "Direct Execution (No Fallback)"}
            </p>
          </div>
        </div>
      </div>

      {/* Grid 1: Provider & Subsystem Status */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Card>
          <p className="text-xs font-mono uppercase tracking-widest text-slate-light">Embedding Provider</p>
          <p className="text-xl font-display font-semibold mt-2">{health.embedding_provider}</p>
          <p className="text-xs text-slate-light mt-1">Dimension: 16 (Deterministic)</p>
        </Card>
        <Card>
          <p className="text-xs font-mono uppercase tracking-widest text-slate-light">Vector Store</p>
          <p className="text-xl font-display font-semibold mt-2">{health.vector_store}</p>
          <p className="text-xs text-slate-light mt-1">pgvector ready fallback</p>
        </Card>
        <Card>
          <p className="text-xs font-mono uppercase tracking-widest text-slate-light">OCR Engine</p>
          <p className="text-xl font-display font-semibold mt-2">{health.ocr_provider}</p>
          <p className="text-xs text-slate-light mt-1">Structured document extractor</p>
        </Card>
        <Card>
          <p className="text-xs font-mono uppercase tracking-widest text-slate-light">Pipeline Version</p>
          <p className="text-xl font-display font-semibold mt-2">v{health.pipeline_version}</p>
          <p className="text-xs text-slate-light mt-1">Part 2.6 Architecture</p>
        </Card>
      </div>

      {/* Grid 2: Governance & Human-AI Agreement */}
      {evaluation && (
        <div className="grid lg:grid-cols-3 gap-6 mb-8">
          <Card className="lg:col-span-2">
            <h3 className="font-semibold text-sm mb-4">Governance & Human-AI Agreement</h3>
            <div className="grid sm:grid-cols-3 gap-4 mb-6">
              <div className="p-3 bg-paper rounded-lg border border-line">
                <p className="text-xs text-slate-light">Human-AI Agreement</p>
                <p className="text-2xl font-display font-semibold mt-1">
                  {evaluation.human_ai_agreement != null ? `${(evaluation.human_ai_agreement * 100).toFixed(1)}%` : "N/A"}
                </p>
              </div>
              <div className="p-3 bg-paper rounded-lg border border-line">
                <p className="text-xs text-slate-light">Human Override Rate</p>
                <p className="text-2xl font-display font-semibold mt-1">
                  {evaluation.override_rate != null ? `${(evaluation.override_rate * 100).toFixed(1)}%` : "0%"}
                </p>
              </div>
              <div className="p-3 bg-paper rounded-lg border border-line">
                <p className="text-xs text-slate-light">Human Review Triggers</p>
                <p className="text-2xl font-display font-semibold mt-1">
                  {evaluation.review_required_rate != null ? `${(evaluation.review_required_rate * 100).toFixed(1)}%` : "N/A"}
                </p>
              </div>
            </div>

            {/* Agreement by Confidence Band */}
            {evaluation.agreement_by_confidence_band && (
              <div>
                <h4 className="text-xs font-mono uppercase text-slate-light mb-2">Agreement by Confidence Band</h4>
                <div className="space-y-2">
                  {Object.entries(evaluation.agreement_by_confidence_band).map(([band, data]) => (
                    <div key={band} className="flex items-center justify-between p-2 rounded bg-paper text-sm">
                      <span className="font-mono text-xs">{band} Confidence</span>
                      <span className="text-slate-light text-xs">Samples: {data.sample_size}</span>
                      <span className="font-medium text-teal">
                        {data.agreement != null ? `${(data.agreement * 100).toFixed(0)}%` : "N/A"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>

          <Card>
            <h3 className="font-semibold text-sm mb-3">Confidence Calibration</h3>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-light">Calibration Status</span>
                <span className="font-mono text-xs font-medium text-teal">
                  {evaluation.confidence_calibration?.calibration_status || "INSUFFICIENT_DATA"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-light">Average Confidence</span>
                <span className="font-medium">
                  {evaluation.avg_confidence != null ? `${(evaluation.avg_confidence * 100).toFixed(1)}%` : "N/A"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-light">Brier Calibration Score</span>
                <span className="font-medium">
                  {evaluation.confidence_calibration?.brier_score != null ? evaluation.confidence_calibration.brier_score.toFixed(4) : "N/A"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-light">Evaluation Sample Size</span>
                <span className="font-medium">{evaluation.evaluation_sample_size}</span>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Grid 3: Retrieval Quality Metrics */}
      {retrieval && (
        <Card>
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-sm">Historical Retrieval Metrics (Top-K)</h3>
            <span className="text-xs font-mono text-slate-light">Status: {retrieval.status}</span>
          </div>
          {retrieval.status === "insufficient_ground_truth" ? (
            <p className="text-xs text-slate-light italic">
              Insufficient ground truth dataset size to compute scientific retrieval metrics ({retrieval.dataset_size} cases available).
            </p>
          ) : (
            <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-4 text-center">
              <div className="p-3 bg-paper rounded-lg border border-line">
                <p className="text-xs text-slate-light">Precision@1</p>
                <p className="text-xl font-display font-semibold mt-1">
                  {retrieval.precision_at_1 != null ? `${(retrieval.precision_at_1 * 100).toFixed(0)}%` : "N/A"}
                </p>
              </div>
              <div className="p-3 bg-paper rounded-lg border border-line">
                <p className="text-xs text-slate-light">Precision@3</p>
                <p className="text-xl font-display font-semibold mt-1">
                  {retrieval.precision_at_3 != null ? `${(retrieval.precision_at_3 * 100).toFixed(0)}%` : "N/A"}
                </p>
              </div>
              <div className="p-3 bg-paper rounded-lg border border-line">
                <p className="text-xs text-slate-light">Precision@5</p>
                <p className="text-xl font-display font-semibold mt-1">
                  {retrieval.precision_at_5 != null ? `${(retrieval.precision_at_5 * 100).toFixed(0)}%` : "N/A"}
                </p>
              </div>
              <div className="p-3 bg-paper rounded-lg border border-line">
                <p className="text-xs text-slate-light">MRR</p>
                <p className="text-xl font-display font-semibold mt-1">
                  {retrieval.mrr != null ? retrieval.mrr.toFixed(3) : "N/A"}
                </p>
              </div>
              <div className="p-3 bg-paper rounded-lg border border-line">
                <p className="text-xs text-slate-light">Avg Similarity</p>
                <p className="text-xl font-display font-semibold mt-1">
                  {retrieval.average_similarity != null ? `${(retrieval.average_similarity * 100).toFixed(0)}%` : "N/A"}
                </p>
              </div>
            </div>
          )}
        </Card>
      )}
    </AdminLayout>
  );
}
