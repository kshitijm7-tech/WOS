import { AIAnalysis } from "../types/api";

function formatConfidence(c?: number | null) {
  if (c == null) return "—";
  return `${(c * 100).toFixed(0)}%`;
}

export default function AIAnalysisCard({ analysis, onStart }: { analysis: AIAnalysis | null; onStart?: () => void }) {
  if (!analysis) {
    return (
      <div className="bg-white border border-line rounded-xl p-5">
        <h3 className="font-semibold text-sm">AI Recommendation</h3>
        <p className="text-sm text-slate-light mt-2">No analysis yet.</p>
        {onStart && <button onClick={onStart} className="mt-3 bg-ink text-paper px-4 py-2 rounded-md text-sm">Start AI Analysis</button>}
      </div>
    );
  }

  const status = analysis.ai_analysis_status;

  if (status === "PENDING") {
    return (
      <div className="bg-white border border-line rounded-xl p-5">
        <h3 className="font-semibold text-sm">AI Recommendation</h3>
        <p className="text-sm text-slate-light mt-2">AI analysis pending.</p>
        <p className="text-xs text-slate-light mt-1">Deterministic warranty check already completed. AI will add evidence interpretation and recommendation.</p>
        {onStart && <button onClick={onStart} className="mt-3 bg-ink text-paper px-4 py-2 rounded-md text-sm">Start AI Analysis</button>}
      </div>
    );
  }

  if (status === "RUNNING") {
    return (
      <div className="bg-white border border-line rounded-xl p-5">
        <h3 className="font-semibold text-sm">AI Recommendation</h3>
        <div className="flex items-center gap-2 mt-3">
          <div className="h-5 w-5 rounded-full border-2 border-line border-t-ink animate-spin" />
          <span className="text-sm text-slate">AI analysis in progress…</span>
        </div>
        <p className="text-xs text-slate-light mt-2">MockRocketRideClient running 6 stages (offline). Will complete shortly.</p>
      </div>
    );
  }

  if (status === "FAILED") {
    return (
      <div className="bg-white border border-line rounded-xl p-5">
        <h3 className="font-semibold text-sm">AI Recommendation</h3>
        <p className="text-sm text-alert mt-2">AI analysis unavailable — manual review required.</p>
        <p className="text-xs text-slate-light mt-1">{analysis.ai_analysis_error || "Analysis failed. Claim remains operational; deterministic warranty is authoritative."}</p>
        {onStart && <button onClick={onStart} className="mt-3 border border-line px-4 py-2 rounded-md text-sm">Retry AI Analysis</button>}
      </div>
    );
  }

  if (status === "COMPLETED" && analysis.decision) {
    const d = analysis.decision;
    return (
      <div className="bg-white border border-line rounded-xl p-5">
        <h3 className="font-semibold text-sm">AI Recommendation</h3>
        <div className="mt-3 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${d.recommendation === "DENY" ? "bg-alert-soft text-alert" : d.recommendation === "HUMAN_REVIEW" ? "bg-amber-soft text-amber" : "bg-teal-soft text-teal"}`}>{d.recommendation}</span>
            <span className="text-sm font-mono">{formatConfidence(d.confidence)} confidence</span>
            {d.confidence_band && <span className={`text-xs px-2 py-1 rounded border ${d.confidence_band === "HIGH" ? "bg-teal-soft text-teal border-teal/20" : d.confidence_band === "MEDIUM" ? "bg-amber-soft text-amber border-amber/20" : "bg-alert-soft text-alert border-alert/20"}`}>{d.confidence_band}</span>}
            {d.requires_human_review && <span className="text-xs px-2 py-1 rounded bg-amber-soft text-amber border border-amber/20">Human review required</span>}
          </div>
          {d.decision_score != null && (
            <div className="text-xs">
              <span className="font-semibold text-slate-dark">Decision Score:</span> <span className="font-mono">{d.decision_score.toFixed(3)}</span> <span className="text-slate-light">/ 1.0</span>
            </div>
          )}
          <div className="text-sm">
            <p className="text-xs font-semibold text-slate-dark">Validation</p>
            <p className={`text-xs mt-1 ${d.validation_status === "VALID" ? "text-teal" : d.validation_status === "INVALID" ? "text-alert" : "text-amber"}`}>{d.validation_status} {d.validation_status === "REQUIRES_HUMAN_REVIEW" ? "— validator requires human" : ""}</p>
            {d.validation_errors && d.validation_errors.length > 0 && <pre className="text-xs bg-paper border border-line rounded p-2 mt-1 overflow-auto">{JSON.stringify(d.validation_errors, null, 2)}</pre>}
          </div>
          {d.explanation && (
            <div className="bg-paper border border-line rounded p-3">
              <p className="text-xs font-semibold text-slate-dark">Explanation</p>
              <p className="text-sm text-ink mt-1">{d.explanation.summary}</p>
              {d.explanation.reasoning_factors.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs font-semibold">Reasoning factors</p>
                  <ul className="text-xs list-disc pl-4 mt-1">
                    {d.explanation.reasoning_factors.map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                </div>
              )}
              {d.explanation.confidence_explanation && <p className="text-xs text-slate-light mt-2">{d.explanation.confidence_explanation}</p>}
            </div>
          )}
          {d.conflicts && d.conflicts.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-dark">Conflicts</p>
              <ul className="text-sm list-disc pl-4 mt-1 text-alert">
                {d.conflicts.map((c, i) => <li key={i}>{c.conflict_code}: {c.description} ({c.severity})</li>)}
              </ul>
            </div>
          )}
          {d.evidence.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-dark">Supporting evidence</p>
              <ul className="text-sm list-disc pl-4 mt-1">
                {d.evidence.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            </div>
          )}
          {d.risk_flags.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-dark">Risk flags</p>
              <ul className="text-sm list-disc pl-4 mt-1 text-alert">
                {d.risk_flags.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </div>
          )}
          {d.missing_information.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-dark">Missing information</p>
              <ul className="text-sm list-disc pl-4 mt-1">
                {d.missing_information.map((m, i) => <li key={i}>{m}</li>)}
              </ul>
            </div>
          )}
          <p className="text-xs text-slate-light">Model: {d.model || "mock"} · v{d.decision_version || 1} · {analysis.stages.length} stages {d.explanation?.historical_case_references?.length ? `· ${d.explanation.historical_case_references.length} similar cases` : ""}</p>
          <div className="mt-2 text-xs text-slate-light border-t border-line pt-2">
            <p className="font-semibold">Intelligence Sources</p>
            <ul className="list-disc pl-4 mt-1">
              <li>Evidence: {d.evidence.length} items {d.missing_information.length ? `· Missing: ${d.missing_information.slice(0,2).join(", ")}` : "· Complete"}</li>
              <li>Policy: {d.explanation?.policy_references?.length || 0} references</li>
              <li>Historical: {d.explanation?.historical_case_references?.length || 0} similar cases</li>
              <li>Risk: {d.risk_flags.length} signals</li>
              <li>OCR: {d.model === "mock" ? "Mock extraction" : "Real OCR"} · Confidence {d.confidence.toFixed(2)}</li>
            </ul>
            <p className="mt-2 font-mono">Provider: {d.model?.includes("mock") ? "Mock" : d.model} · Pipeline: 2.5 · Governance Score: {d.decision_score?.toFixed(3) || "—"}</p>
          </div>
          {analysis.stages.length > 0 && (
            <details className="mt-2">
              <summary className="text-xs text-teal cursor-pointer">Show 6 stage outputs</summary>
              <div className="mt-2 space-y-2">
                {analysis.stages.map((s) => (
                  <div key={s.stage} className="bg-paper border border-line rounded p-2">
                    <p className="text-xs font-mono font-semibold">{s.stage}</p>
                    <pre className="text-xs overflow-auto mt-1 max-h-32">{JSON.stringify(s.result, null, 2)}</pre>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white border border-line rounded-xl p-5">
      <h3 className="font-semibold text-sm">AI Recommendation</h3>
      <p className="text-sm text-slate-light mt-2">No decision yet.</p>
    </div>
  );
}
