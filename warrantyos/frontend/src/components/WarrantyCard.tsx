import { Claim } from "../types/api";

export default function WarrantyCard({ claim }: { claim: Claim }) {
  const eligible = claim.warranty_eligible;
  const isEligible = eligible === true;
  const isNotEligible = eligible === false;

  return (
    <div className="bg-white border border-line rounded-xl shadow-card p-5">
      <h3 className="font-display font-semibold text-sm mb-1">Warranty Eligibility</h3>
      <p className="text-xs text-slate-light mb-4">Deterministic — no AI involved in this phase</p>

      {eligible === null || eligible === undefined ? (
        <div className="rounded-md bg-amber-soft border border-amber/20 p-3 text-sm text-ink">Warranty check pending.</div>
      ) : (
        <div className={`rounded-lg border p-4 ${isEligible ? "bg-teal-soft border-teal/20" : isNotEligible ? "bg-alert-soft border-alert/20" : "bg-paper"}`}>
          <div className={`text-sm font-semibold ${isEligible ? "text-teal" : "text-alert"}`}>
            {isEligible ? "Eligible" : "Not Eligible"} {claim.warranty?.warranty_active ? "· Warranty Active" : "· Warranty Inactive"}
          </div>
          {claim.eligibility_reason && <p className="text-sm text-ink mt-2">{claim.eligibility_reason}</p>}
          {claim.purchase_date && <p className="text-xs text-slate mt-2 font-mono">Purchase: {claim.purchase_date}</p>}
        </div>
      )}

      {claim.exclusions_triggered && claim.exclusions_triggered.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold text-slate-dark">Exclusions triggered</p>
          <ul className="text-sm text-alert list-disc pl-4 mt-1">
            {claim.exclusions_triggered.map((ex, i) => (
              <li key={i}>{ex}</li>
            ))}
          </ul>
        </div>
      )}

      {claim.missing_information && claim.missing_information.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold text-slate-dark">Missing information</p>
          <ul className="text-sm text-ink list-disc pl-4 mt-1">
            {claim.missing_information.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </div>
      )}

      {isNotEligible && (
        <p className="text-xs text-slate-light mt-4">This is a deterministic rules check. An admin will review before any denial is final.</p>
      )}
    </div>
  );
}
