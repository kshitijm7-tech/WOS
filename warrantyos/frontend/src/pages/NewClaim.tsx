import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import CustomerLayout from "../layouts/CustomerLayout";
import { api, ApiError } from "../lib/api";
import { ProductSerial } from "../types/api";
import { Card, Button, Loading, ErrorState } from "../components/ui";

const FAULT_CATEGORIES = ["motor", "compressor", "display", "pump", "leak", "overheat", "heating", "other"];

export default function NewClaim() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [step, setStep] = useState(1);
  const [serials, setSerials] = useState<ProductSerial[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [selectedSerial, setSelectedSerial] = useState<string>(params.get("serial") || "");
  const [selectedProductId, setSelectedProductId] = useState<number | null>(params.get("product") ? Number(params.get("product")) : null);
  const [faultCategory, setFaultCategory] = useState("motor");
  const [faultDescription, setFaultDescription] = useState("");
  const [evidenceFiles, setEvidenceFiles] = useState<{ file: File; type: string }[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [created, setCreated] = useState<{ claim_code: string; id: number; status: string; warranty_eligible: boolean | null; eligibility_reason: string | null } | null>(null);
  const [uploadState, setUploadState] = useState<Record<string, string>>({});

  useEffect(() => {
    api.get<ProductSerial[]>("/products/serials/mine").then(setSerials).catch((e) => setError(e instanceof ApiError ? e.message : "Failed"));
  }, []);

  const selected = serials?.find((s) => s.serial_number === selectedSerial) || null;

  async function handleSubmit() {
    setSubmitError(null);
    if (!selectedSerial || !selectedProductId) {
      setSubmitError("Select a product serial.");
      return;
    }
    if (faultDescription.trim().length < 10) {
      setSubmitError("Fault description must be at least 10 characters.");
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        product_id: selectedProductId,
        serial_number: selectedSerial,
        fault_description: faultDescription,
        fault_category: faultCategory,
      };
      const res = await api.post<{ claim_code: string; id: number; status: string; warranty_eligible: boolean | null; eligibility_reason: string | null }>("/claims", payload);
      setCreated(res);
      // upload evidence after creation
      for (const { file, type } of evidenceFiles) {
        const key = file.name;
        setUploadState((m) => ({ ...m, [key]: "uploading" }));
        try {
          const fd = new FormData();
          fd.append("file", file);
          fd.append("evidence_type", type);
          await api.upload(`/claims/${res.id}/evidence`, fd);
          setUploadState((m) => ({ ...m, [key]: "success" }));
        } catch (e) {
          const msg = e instanceof ApiError ? e.message : "Upload failed";
          setUploadState((m) => ({ ...m, [key]: `error: ${msg}` }));
        }
      }
      setStep(5);
    } catch (e) {
      setSubmitError(e instanceof ApiError ? e.message : "Failed to create claim");
    } finally {
      setSubmitting(false);
    }
  }

  if (!serials) {
    if (error) return <CustomerLayout><ErrorState message={error} /></CustomerLayout>;
    return <CustomerLayout><Loading /></CustomerLayout>;
  }

  if (created && step === 5) {
    return (
      <CustomerLayout>
        <Card className="max-w-2xl mx-auto text-center">
          <p className="text-xs font-mono text-teal uppercase tracking-widest">Warranty Claim Submitted</p>
          <h1 className="font-display font-semibold text-2xl mt-2">{created.claim_code}</h1>
          <p className="text-sm text-slate-light mt-2">Status: <span className="font-mono font-medium text-ink">{created.status}</span></p>
          <div className={`mt-4 rounded-lg border p-4 text-left ${created.warranty_eligible ? "bg-teal-soft border-teal/20" : "bg-alert-soft border-alert/20"}`}>
            <p className={`text-sm font-semibold ${created.warranty_eligible ? "text-teal" : "text-alert"}`}>{created.warranty_eligible ? "Eligible" : "Not Eligible"}</p>
            <p className="text-sm text-ink mt-1">{created.eligibility_reason}</p>
          </div>
          <div className="mt-6 flex justify-center gap-3">
            <Button onClick={() => navigate(`/customer/claims/${created.id}`)}>View Claim</Button>
            <Button variant="secondary" onClick={() => navigate("/customer/claims")}>My Claims</Button>
          </div>
          {Object.keys(uploadState).length > 0 && (
            <div className="mt-6 text-left">
              <p className="text-sm font-medium mb-2">Evidence upload</p>
              {Object.entries(uploadState).map(([name, st]) => (
                <p key={name} className={`text-xs ${st === "success" ? "text-teal" : st.startsWith("error") ? "text-alert" : "text-slate"}`}>
                  {name}: {st}
                </p>
              ))}
            </div>
          )}
        </Card>
      </CustomerLayout>
    );
  }

  return (
    <CustomerLayout>
      <div className="max-w-3xl mx-auto">
        <h1 className="font-display font-semibold text-2xl">New Warranty Claim</h1>
        <p className="text-sm text-slate-light mt-1">Deterministic warranty check — no AI yet. Evidence is optional at submission.</p>

        <div className="flex items-center gap-2 mt-6 mb-6 text-xs font-mono">
          {[1, 2, 3, 4].map((s) => (
            <div key={s} className={`h-8 w-8 rounded-full flex items-center justify-center border ${step === s ? "bg-ink text-paper border-ink" : step > s ? "bg-teal text-paper border-teal" : "bg-paper text-slate-light border-line"}`}>
              {s}
            </div>
          ))}
          <span className="ml-2 text-slate">{["Product", "Issue", "Evidence", "Review"][step - 1]}</span>
        </div>

        {step === 1 && (
          <Card>
            <h3 className="font-semibold mb-4">Step 1 — Select Product</h3>
            <p className="text-sm text-slate-light mb-3">Only products you own are shown.</p>
            <div className="space-y-2">
              {serials.map((s) => (
                <label key={s.id} className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer ${selectedSerial === s.serial_number ? "border-ink bg-paper" : "border-line hover:bg-paper"}`}>
                  <div>
                    <p className="text-sm font-medium">{s.product_name}</p>
                    <p className="text-xs font-mono text-slate-light">{s.serial_number} · {s.product_sku} · {s.purchase_date}</p>
                  </div>
                  <input type="radio" name="serial" checked={selectedSerial === s.serial_number} onChange={() => { setSelectedSerial(s.serial_number); setSelectedProductId(s.product_id); }} />
                </label>
              ))}
            </div>
            {selected && <p className="text-xs text-teal mt-3">Selected: {selected.product_name} — {selected.serial_number} — warranty active depends on purchase date.</p>}
            <div className="mt-6 flex justify-end">
              <Button onClick={() => setStep(2)} disabled={!selectedSerial}>Continue</Button>
            </div>
          </Card>
        )}

        {step === 2 && (
          <Card>
            <h3 className="font-semibold mb-4">Step 2 — Describe Issue</h3>
            <label className="block">
              <span className="text-sm font-medium">Fault category</span>
              <select value={faultCategory} onChange={(e) => setFaultCategory(e.target.value)} className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm">
                {FAULT_CATEGORIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </label>
            <label className="block mt-4">
              <span className="text-sm font-medium">Fault description</span>
              <textarea value={faultDescription} onChange={(e) => setFaultDescription(e.target.value)} placeholder="e.g., Washing machine drum not spinning, loud grinding noise for 2 days, motor seems to fail intermittently..." className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm min-h-[120px]" />
              <span className="text-xs text-slate-light">At least 10 characters. Be specific — this drives the deterministic warranty check (exclusions are matched against this text).</span>
            </label>
            <div className="mt-6 flex justify-between">
              <Button variant="secondary" onClick={() => setStep(1)}>Back</Button>
              <Button onClick={() => setStep(3)} disabled={faultDescription.trim().length < 10}>Continue</Button>
            </div>
          </Card>
        )}

        {step === 3 && (
          <Card>
            <h3 className="font-semibold mb-4">Step 3 — Evidence (optional)</h3>
            <p className="text-sm text-slate-light mb-3">Invoice, photo, video, or other. Allowed: jpg, png, webp, pdf, mp4, mov, txt. Max 20 MB per file. You can also upload after submission.</p>
            <div className="space-y-3">
              {[
                { type: "INVOICE", label: "Invoice (PDF, JPG)" },
                { type: "PHOTO", label: "Photo" },
                { type: "VIDEO", label: "Video" },
              ].map((cfg) => (
                <label key={cfg.type} className="block">
                  <span className="text-xs font-medium">{cfg.label} — {cfg.type}</span>
                  <input type="file" onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) setEvidenceFiles((prev) => [...prev, { file: f, type: cfg.type }]);
                  }} className="mt-1 block w-full text-sm" accept={cfg.type==="INVOICE" ? ".pdf,.jpg,.png" : cfg.type==="PHOTO" ? "image/*" : "video/*"} />
                </label>
              ))}
            </div>
            {evidenceFiles.length > 0 && (
              <div className="mt-4 space-y-1">
                {evidenceFiles.map((ef, i) => (
                  <div key={i} className="flex items-center justify-between text-xs bg-paper border border-line rounded px-2 py-1">
                    <span>{ef.file.name} · {(ef.file.size/1024).toFixed(1)} KB · {ef.type}</span>
                    <button onClick={() => setEvidenceFiles((prev) => prev.filter((_, idx) => idx !== i))} className="text-alert">remove</button>
                  </div>
                ))}
              </div>
            )}
            <div className="mt-6 flex justify-between">
              <Button variant="secondary" onClick={() => setStep(2)}>Back</Button>
              <Button onClick={() => setStep(4)}>Continue</Button>
            </div>
          </Card>
        )}

        {step === 4 && (
          <Card>
            <h3 className="font-semibold mb-4">Step 4 — Review</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-slate-light">Product</span><span className="font-medium">{selected?.product_name}</span></div>
              <div className="flex justify-between"><span className="text-slate-light">Serial</span><span className="font-mono">{selectedSerial}</span></div>
              <div className="flex justify-between"><span className="text-slate-light">Purchase date</span><span>{selected?.purchase_date || "—"}</span></div>
              <div className="flex justify-between"><span className="text-slate-light">Fault category</span><span>{faultCategory}</span></div>
              <div className="pt-2 border-t border-line"><span className="text-slate-light text-xs">Fault description</span><p className="text-sm text-ink mt-1">{faultDescription}</p></div>
              <div><span className="text-slate-light text-xs">Evidence</span><p className="text-sm">{evidenceFiles.length ? evidenceFiles.map((ef) => `${ef.file.name} (${ef.type})`).join(", ") : "None — can upload later"}</p></div>
            </div>
            {submitError && <p className="text-sm text-alert bg-alert-soft rounded px-3 py-2 mt-4">{submitError}</p>}
            <div className="mt-6 flex justify-between">
              <Button variant="secondary" onClick={() => setStep(3)}>Back</Button>
              <Button onClick={handleSubmit} disabled={submitting}>{submitting ? "Submitting…" : "Submit Warranty Claim"}</Button>
            </div>
          </Card>
        )}
      </div>
    </CustomerLayout>
  );
}
