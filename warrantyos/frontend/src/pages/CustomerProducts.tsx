import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import CustomerLayout from "../layouts/CustomerLayout";
import { api, ApiError } from "../lib/api";
import { ProductSerial } from "../types/api";
import { Loading, ErrorState, Empty, Card } from "../components/ui";

export default function CustomerProducts() {
  const [serials, setSerials] = useState<ProductSerial[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const data = await api.get<ProductSerial[]>("/products/serials/mine");
      setSerials(data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load");
    }
  }
  useEffect(() => { load(); }, []);

  if (!serials) {
    if (error) return <CustomerLayout><ErrorState message={error} onRetry={load} /></CustomerLayout>;
    return <CustomerLayout><Loading /></CustomerLayout>;
  }

  return (
    <CustomerLayout>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-display font-semibold text-2xl">My Products</h1>
          <p className="text-sm text-slate-light mt-1">Real products by serial ownership · {serials.length} units</p>
        </div>
        <Link to="/customer/claims/new" className="hidden sm:inline-flex bg-ink text-paper px-4 py-2.5 rounded-md text-sm font-medium">Start Warranty Claim</Link>
      </div>

      {serials.length === 0 ? (
        <Empty title="No products yet." body="Your owned serials will appear here. Seed data includes 3 for demo.customer." />
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {serials.map((s) => {
            const warrantyEnd = (() => {
              if (!s.purchase_date) return null;
              // Simple display: purchase + 12/24 months not computed client-side accurately; show purchase
              return null;
            })();
            return (
              <Card key={s.id}>
                <p className="text-xs font-mono text-slate-light">{s.product_sku || `PID ${s.product_id}`}</p>
                <h3 className="font-semibold text-ink mt-1">{s.product_name || "Product"}</h3>
                <div className="mt-3 space-y-1.5 text-sm">
                  <div className="flex justify-between"><span className="text-slate-light">Serial</span><span className="font-mono font-medium">{s.serial_number}</span></div>
                  <div className="flex justify-between"><span className="text-slate-light">Purchase</span><span>{s.purchase_date || "—"}</span></div>
                  <div className="flex justify-between"><span className="text-slate-light">Retailer</span><span>{s.retailer || "—"}</span></div>
                  {warrantyEnd && <div className="text-xs text-slate-light">Warranty end: {warrantyEnd}</div>}
                </div>
                <Link to={`/customer/claims/new?serial=${encodeURIComponent(s.serial_number)}&product=${s.product_id}`} className="mt-4 block text-center rounded-md border border-teal text-teal text-sm font-medium py-2 hover:bg-teal-soft">
                  Start Warranty Claim
                </Link>
              </Card>
            );
          })}
        </div>
      )}
    </CustomerLayout>
  );
}
