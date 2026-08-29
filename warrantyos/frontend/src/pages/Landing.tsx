import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { pingDatabase } from "../lib/api";

/** A quiet diagnostic-pulse line — the page's signature motif, echoed in status badges
 * and the claim timeline throughout the product. Represents a fault signal being read. */
function PulseLine() {
  return (
    <svg viewBox="0 0 400 60" className="w-full max-w-md" aria-hidden="true">
      <polyline
        points="0,30 60,30 80,10 100,50 120,30 200,30 220,14 236,46 252,30 400,30"
        fill="none"
        stroke="#E8A33D"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function Landing() {
  const [dbStatus, setDbStatus] = useState<"checking" | "connected" | "offline">("checking");

  useEffect(() => {
    pingDatabase()
      .then(() => setDbStatus("connected"))
      .catch(() => setDbStatus("offline"));
  }, []);

  return (
    <div className="min-h-screen bg-ink text-paper">
      <nav className="flex items-center justify-between px-8 py-6 max-w-6xl mx-auto">
        <div className="font-display font-semibold text-lg tracking-tight">
          Warranty<span className="text-amber">OS</span>
        </div>
        <div
          className="hidden sm:flex items-center gap-2 text-xs font-mono text-slate-light"
          title="Backend connectivity (Phase 1 smoke check)"
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              dbStatus === "connected" ? "bg-teal" : dbStatus === "offline" ? "bg-alert" : "bg-amber"
            }`}
          />
          {dbStatus === "connected" && "api + db online"}
          {dbStatus === "offline" && "api offline"}
          {dbStatus === "checking" && "checking status…"}
        </div>
      </nav>

      <header className="max-w-6xl mx-auto px-8 pt-16 pb-24 grid gap-10 lg:grid-cols-2 items-center">
        <div>
          <span className="font-mono text-xs text-amber tracking-widest uppercase">
            Warranty &amp; Returns Operations
          </span>
          <h1 className="font-display font-semibold text-4xl sm:text-5xl leading-[1.1] mt-4">
            Every claim gets a verdict.
            <br />
            Every denial gets a human.
          </h1>
          <p className="mt-6 text-slate-light text-lg max-w-lg">
            WarrantyOS reads the fault, checks the warranty, searches the history, and
            recommends repair, replace, refund, or deny — then routes anything risky,
            high-value, or denied to a person before it becomes final.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              to="/login"
              className="rounded-md bg-amber text-ink font-medium px-5 py-2.5 hover:brightness-95 transition"
            >
              Customer Login
            </Link>
            <Link
              to="/admin/login"
              className="rounded-md border border-slate-dark px-5 py-2.5 font-medium hover:bg-white/5 transition"
            >
              Admin Login
            </Link>
            <Link
              to="/register"
              className="rounded-md px-5 py-2.5 font-medium text-slate-light hover:text-paper transition"
            >
              Create customer account →
            </Link>
          </div>
          <div className="mt-10">
            <PulseLine />
            <p className="font-mono text-xs text-slate-light mt-2">
              claim WR-10482 — signal read, evidence stable
            </p>
          </div>
        </div>

        <div className="rounded-xl border border-slate-dark bg-white/5 p-6 shadow-card">
          <p className="font-mono text-xs text-slate-light mb-4">CLAIM #WR-10482</p>
          <div className="space-y-3 text-sm">
            <Row label="Product" value="Washing Machine X1" />
            <Row label="Serial" value="WMX-98234" mono />
            <Row label="Warranty" value="ACTIVE" tone="teal" />
            <Row label="Recommendation" value="REPAIR" tone="amber" />
            <Row label="Confidence" value="91%" />
          </div>
          <div className="mt-5 pt-5 border-t border-slate-dark/60">
            <p className="text-xs text-slate-light mb-2">Evidence</p>
            <ul className="text-sm space-y-1.5 text-paper/90">
              <li>· Warranty is active, invoice verified</li>
              <li>· Fault consistent with a covered issue</li>
              <li>· 17 similar historical cases found</li>
            </ul>
          </div>
        </div>
      </header>

      <section className="max-w-6xl mx-auto px-8 pb-24 grid sm:grid-cols-3 gap-6">
        <Feature
          title="Rules decide eligibility"
          body="Warranty windows, serials, and policy exclusions are checked deterministically — never left to a model to infer."
        />
        <Feature
          title="AI reads the evidence"
          body="Fault descriptions, photos, and invoices are interpreted and summarized, with a recommendation, confidence, and reasoning."
        />
        <Feature
          title="Humans close the loop"
          body="Every denial, every high-value claim, every low-confidence or conflicting case goes to a person before it's final."
        />
      </section>
    </div>
  );
}

function Row({
  label,
  value,
  mono,
  tone,
}: {
  label: string;
  value: string;
  mono?: boolean;
  tone?: "teal" | "amber";
}) {
  const toneClass = tone === "teal" ? "text-teal" : tone === "amber" ? "text-amber" : "text-paper";
  return (
    <div className="flex items-center justify-between">
      <span className="text-slate-light">{label}</span>
      <span className={`${mono ? "font-mono" : "font-medium"} ${toneClass}`}>{value}</span>
    </div>
  );
}

function Feature({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-slate-dark/60 p-5">
      <h3 className="font-display font-semibold mb-2">{title}</h3>
      <p className="text-sm text-slate-light">{body}</p>
    </div>
  );
}
