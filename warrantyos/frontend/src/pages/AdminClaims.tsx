import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AdminLayout from "../layouts/AdminLayout";
import { api, ApiError } from "../lib/api";
import { Claim } from "../types/api";
import StatusBadge from "../components/StatusBadge";
import { Loading, ErrorState, Empty, Card } from "../components/ui";

export default function AdminClaims() {
  const [claims, setClaims] = useState<Claim[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [product, setProduct] = useState("");
  const [customer, setCustomer] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  async function load() {
    try {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      if (product) params.set("product_id", product);
      if (customer) params.set("customer_id", customer);
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);
      const qs = params.toString() ? `?${params}` : "";
      const data = await api.get<Claim[]>(`/admin/claims${qs}`);
      setClaims(data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed");
    }
  }
  useEffect(() => { load(); }, []);

  function applyFilters() { load(); }
  function clearFilters() { setStatus(""); setProduct(""); setCustomer(""); setDateFrom(""); setDateTo(""); setTimeout(load, 0); }

  if (!claims) {
    if (error) return <AdminLayout><ErrorState message={error} onRetry={load} /></AdminLayout>;
    return <AdminLayout><Loading /></AdminLayout>;
  }

  return (
    <AdminLayout>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="font-display font-semibold text-2xl">Claims Queue</h1>
          <p className="text-sm text-slate-light">Real claims · {claims.length} results</p>
        </div>
      </div>

      <Card className="mb-6">
        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">
          <select value={status} onChange={(e)=>setStatus(e.target.value)} className="rounded-md border border-line px-2 py-2 text-sm">
            <option value="">All statuses</option>
            {["SUBMITTED","PROCESSING","UNDER_REVIEW","APPROVED","REJECTED","MORE_INFORMATION_REQUIRED","RESOLVED"].map(s=> <option key={s} value={s}>{s}</option>)}
          </select>
          <input placeholder="Product ID" value={product} onChange={(e)=>setProduct(e.target.value)} className="rounded-md border border-line px-3 py-2 text-sm" />
          <input placeholder="Customer ID" value={customer} onChange={(e)=>setCustomer(e.target.value)} className="rounded-md border border-line px-3 py-2 text-sm" />
          <input type="date" value={dateFrom} onChange={(e)=>setDateFrom(e.target.value)} className="rounded-md border border-line px-3 py-2 text-sm" />
          <input type="date" value={dateTo} onChange={(e)=>setDateTo(e.target.value)} className="rounded-md border border-line px-3 py-2 text-sm" />
        </div>
        <div className="flex gap-2 mt-3">
          <button onClick={applyFilters} className="bg-ink text-paper px-4 py-2 rounded-md text-sm">Apply Filters</button>
          <button onClick={clearFilters} className="border border-line px-4 py-2 rounded-md text-sm">Clear</button>
        </div>
        <p className="text-xs text-slate-light mt-2">Filters use backend query params: status, product_id, customer_id, date_from, date_to.</p>
      </Card>

      {claims.length===0 ? <Empty title="No claims match filters." /> : (
        <div className="space-y-3">
          {claims.map((c)=> (
            <Link key={c.id} to={`/admin/claims/${c.id}`} className="block">
              <Card className="hover:shadow-md transition">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono text-sm font-semibold">{c.claim_code}</span>
                  <StatusBadge status={c.status} />
                </div>
                <div className="grid sm:grid-cols-3 gap-2 mt-2 text-xs text-slate-light">
                  <span>Customer #{c.customer_id} · Product #{c.product_id}</span>
                  <span>Serial #{c.serial_id || "—"}</span>
                  <span>{new Date(c.created_at).toLocaleDateString()} → {new Date(c.updated_at).toLocaleDateString()}</span>
                </div>
                <p className="text-sm text-ink mt-2 line-clamp-1">{c.fault_description}</p>
                <p className="text-xs mt-1"><span className={c.warranty_eligible ? "text-teal" : c.warranty_eligible===false ? "text-alert" : "text-slate-light"}>{c.warranty_eligible===null ? "pending" : c.warranty_eligible ? "Eligible" : "Not Eligible"}</span> · {c.eligibility_reason?.slice(0,80)}</p>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </AdminLayout>
  );
}
