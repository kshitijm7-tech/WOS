import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import CustomerLayout from "../layouts/CustomerLayout";
import { api, ApiError } from "../lib/api";
import { Claim, ProductSerial } from "../types/api";
import StatusBadge from "../components/StatusBadge";
import { Loading, ErrorState, Empty, Card } from "../components/ui";

export default function CustomerDashboard() {
  const [claims, setClaims] = useState<Claim[] | null>(null);
  const [serials, setSerials] = useState<ProductSerial[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const [c, s] = await Promise.all([
        api.get<Claim[]>("/claims"),
        api.get<ProductSerial[]>("/products/serials/mine"),
      ]);
      setClaims(c);
      setSerials(s);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load dashboard");
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (!claims || !serials) {
    if (error) return <CustomerLayout><ErrorState message={error} onRetry={load} /></CustomerLayout>;
    return <CustomerLayout><Loading text="Loading your workspace…" /></CustomerLayout>;
  }

  const attention = claims.filter((c) => c.status === "MORE_INFORMATION_REQUIRED" || c.status === "REJECTED");
  const recent = [...claims].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()).slice(0, 4);

  return (
    <CustomerLayout>
      <div className="mb-6">
        <h1 className="font-display font-semibold text-2xl text-ink">Customer Dashboard</h1>
        <p className="text-sm text-slate-light mt-1">Real warranty claims, real products — no demo numbers.</p>
      </div>

      <div className="grid sm:grid-cols-3 gap-4 mb-8">
        <Card>
          <p className="text-xs font-mono text-slate-light uppercase tracking-widest">My Products</p>
          <p className="text-3xl font-display font-semibold mt-2">{serials.length}</p>
          <Link to="/customer/products" className="text-sm text-teal mt-2 inline-block">View products →</Link>
        </Card>
        <Card>
          <p className="text-xs font-mono text-slate-light uppercase tracking-widest">My Claims</p>
          <p className="text-3xl font-display font-semibold mt-2">{claims.length}</p>
          <Link to="/customer/claims" className="text-sm text-teal mt-2 inline-block">View claims →</Link>
        </Card>
        <Card>
          <p className="text-xs font-mono text-slate-light uppercase tracking-widest">Requiring Attention</p>
          <p className={`text-3xl font-display font-semibold mt-2 ${attention.length ? "text-alert" : "text-teal"}`}>{attention.length}</p>
          <p className="text-xs text-slate-light mt-1">MORE_INFO / REJECTED</p>
        </Card>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <Card>
          <h3 className="font-semibold text-sm mb-4">Recently Updated Claims</h3>
          {claims.length === 0 ? (
            <Empty title="No warranty claims yet." body="Your claims will appear here after you submit one." action={<Link to="/customer/claims/new" className="text-teal text-sm font-medium">Start a claim →</Link>} />
          ) : (
            <div className="space-y-3">
              {recent.map((c) => (
                <Link key={c.id} to={`/customer/claims/${c.id}`} className="flex items-center justify-between p-3 rounded-lg border border-line hover:bg-paper transition">
                  <div className="min-w-0">
                    <p className="font-mono text-sm font-medium">{c.claim_code}</p>
                    <p className="text-xs text-slate-light truncate">{c.fault_category || "—"} · {new Date(c.updated_at).toLocaleDateString()}</p>
                  </div>
                  <StatusBadge status={c.status} />
                </Link>
              ))}
            </div>
          )}
        </Card>

        <Card>
          <h3 className="font-semibold text-sm mb-4">My Products</h3>
          {serials.length === 0 ? (
            <Empty title="No products found." body="Products are assigned via serial ownership. Contact support if missing." />
          ) : (
            <div className="space-y-3">
              {serials.slice(0, 4).map((s) => (
                <div key={s.id} className="flex items-center justify-between p-3 rounded-lg border border-line">
                  <div>
                    <p className="text-sm font-medium">{s.product_name || `Product #${s.product_id}`}</p>
                    <p className="text-xs font-mono text-slate-light">{s.serial_number} · {s.purchase_date || "no date"}</p>
                  </div>
                  <Link to="/customer/claims/new" className="text-xs text-teal border border-teal/20 rounded px-2 py-1 hover:bg-teal-soft">
                    Claim
                  </Link>
                </div>
              ))}
              {serials.length > 4 && <Link to="/customer/products" className="text-sm text-slate">View all {serials.length} →</Link>}
            </div>
          )}
        </Card>
      </div>
    </CustomerLayout>
  );
}
