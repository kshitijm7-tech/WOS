import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AdminLayout from "../layouts/AdminLayout";
import { api, ApiError } from "../lib/api";
import { Claim } from "../types/api";
import StatusBadge from "../components/StatusBadge";
import { Loading, ErrorState, Card } from "../components/ui";

const STATUSES = ["SUBMITTED","PROCESSING","UNDER_REVIEW","APPROVED","REJECTED","MORE_INFORMATION_REQUIRED","RESOLVED"] as const;

export default function AdminDashboard() {
  const [claims, setClaims] = useState<Claim[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const data = await api.get<Claim[]>("/admin/claims");
      setClaims(data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed");
    }
  }
  useEffect(() => { load(); }, []);

  if (!claims) {
    if (error) return <AdminLayout><ErrorState message={error} onRetry={load} /></AdminLayout>;
    return <AdminLayout><Loading text="Loading operational data…" /></AdminLayout>;
  }

  const total = claims.length;
  const byStatus = Object.fromEntries(STATUSES.map((s) => [s, claims.filter((c) => c.status === s).length]));
  const recent = [...claims].sort((a,b)=> new Date(b.updated_at).getTime()-new Date(a.updated_at).getTime()).slice(0,5);

  return (
    <AdminLayout>
      <div className="mb-6">
        <h1 className="font-display font-semibold text-2xl">Admin Dashboard</h1>
        <p className="text-sm text-slate-light mt-1">Real operational data — no hardcoded numbers.</p>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Card><p className="text-xs font-mono uppercase tracking-widest text-slate-light">Total Claims</p><p className="text-3xl font-display font-semibold mt-2">{total}</p></Card>
        {STATUSES.map((s) => (
          <Card key={s}><p className="text-xs font-mono uppercase tracking-widest text-slate-light">{s.replaceAll("_"," ")}</p><p className="text-2xl font-display font-semibold mt-2">{byStatus[s]}</p></Card>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <h3 className="font-semibold text-sm mb-4">Recently Updated Claims</h3>
          <div className="space-y-2">
            {recent.map((c) => (
              <Link key={c.id} to={`/admin/claims/${c.id}`} className="flex items-center justify-between p-3 rounded-lg border border-line hover:bg-paper">
                <div>
                  <p className="font-mono text-sm font-medium">{c.claim_code}</p>
                  <p className="text-xs text-slate-light">{c.fault_category} · {new Date(c.updated_at).toLocaleDateString()}</p>
                </div>
                <StatusBadge status={c.status} />
              </Link>
            ))}
          </div>
          <Link to="/admin/claims" className="text-sm text-teal mt-4 inline-block">View queue →</Link>
        </Card>
        <Card>
          <h3 className="font-semibold text-sm mb-3">Quick Stats</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-slate-light">Eligible</span><span className="font-medium text-teal">{claims.filter((c)=>c.warranty_eligible).length}</span></div>
            <div className="flex justify-between"><span className="text-slate-light">Not Eligible</span><span className="font-medium text-alert">{claims.filter((c)=>c.warranty_eligible===false).length}</span></div>
            <div className="flex justify-between"><span className="text-slate-light">Pending check</span><span className="font-medium">{claims.filter((c)=>c.warranty_eligible==null).length}</span></div>
          </div>
          <p className="text-xs text-slate-light mt-4">All numbers computed from <code className="font-mono">GET /api/admin/claims</code>.</p>
        </Card>
      </div>
    </AdminLayout>
  );
}
