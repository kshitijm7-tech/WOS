import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import CustomerLayout from "../layouts/CustomerLayout";
import { api, ApiError } from "../lib/api";
import { Claim } from "../types/api";
import StatusBadge from "../components/StatusBadge";
import { Loading, ErrorState, Empty, Card } from "../components/ui";

export default function CustomerClaims() {
  const [claims, setClaims] = useState<Claim[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("");

  async function load() {
    setError(null);
    try {
      const q = filter ? `?status=${filter}` : "";
      const data = await api.get<Claim[]>(`/claims${q}`);
      setClaims(data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed");
    }
  }
  useEffect(() => { load(); }, [filter]);

  if (!claims) {
    if (error) return <CustomerLayout><ErrorState message={error} onRetry={load} /></CustomerLayout>;
    return <CustomerLayout><Loading /></CustomerLayout>;
  }

  return (
    <CustomerLayout>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="font-display font-semibold text-2xl">My Claims</h1>
          <p className="text-sm text-slate-light">Real claims from the database · {claims.length}</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={filter} onChange={(e) => setFilter(e.target.value)} className="rounded-md border border-line px-3 py-2 text-sm">
            <option value="">All statuses</option>
            {["SUBMITTED","PROCESSING","UNDER_REVIEW","APPROVED","REJECTED","MORE_INFORMATION_REQUIRED","RESOLVED"].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <Link to="/customer/claims/new" className="bg-ink text-paper px-4 py-2 rounded-md text-sm font-medium">New Claim</Link>
        </div>
      </div>

      {claims.length === 0 ? (
        <Empty title="No warranty claims yet." body="Create your first claim. It will be checked deterministically." action={<Link to="/customer/claims/new" className="text-teal text-sm">Start a claim →</Link>} />
      ) : (
        <div className="grid gap-4">
          {claims.map((c) => {
            const aiStatus = c.ai_analysis_status || "PENDING";
            const aiLabel =
              aiStatus === "PENDING" ? "AI Pending" :
              aiStatus === "RUNNING" ? "AI Analyzing" :
              aiStatus === "COMPLETED" ? "AI Ready" :
              aiStatus === "FAILED" ? "AI Failed" : aiStatus;
            const aiTone =
              aiStatus === "COMPLETED" ? "bg-teal-soft text-teal border-teal/20" :
              aiStatus === "RUNNING" ? "bg-amber-soft text-amber border-amber/20" :
              aiStatus === "FAILED" ? "bg-alert-soft text-alert border-alert/20" :
              "bg-paper text-slate-light border-line";
            return (
            <Link key={c.id} to={`/customer/claims/${c.id}`} className="block">
              <Card className="hover:shadow-md transition">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono text-sm font-semibold">{c.claim_code}</span>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-1 rounded-full border font-mono ${aiTone}`}>{aiLabel}</span>
                    <StatusBadge status={c.status} />
                  </div>
                </div>
                <p className="text-sm text-ink mt-2 line-clamp-2">{c.fault_description}</p>
                <div className="flex flex-wrap gap-2 mt-3 text-xs text-slate-light">
                  <span>{c.fault_category || "—"}</span>
                  <span>· {new Date(c.created_at).toLocaleDateString()}</span>
                  <span>· {c.warranty_eligible === null ? "pending" : c.warranty_eligible ? "Eligible" : "Not eligible"}</span>
                </div>
                {c.eligibility_reason && <p className="text-xs text-slate-light mt-2 truncate">{c.eligibility_reason}</p>}
              </Card>
            </Link>
          )})}
        </div>
      )}
    </CustomerLayout>
  );
}
