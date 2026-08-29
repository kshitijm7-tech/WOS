import StatusBadge from "./StatusBadge";

const STEPS = ["SUBMITTED", "PROCESSING", "UNDER_REVIEW", "APPROVED", "RESOLVED"] as const;
const ALT = ["REJECTED", "MORE_INFORMATION_REQUIRED"] as const;

export default function StatusStepper({ status }: { status: string }) {
  const all = [...STEPS, ...ALT];
  const idx = all.indexOf(status as typeof all[number]);
  // For stepper, map current to nearest main step
  const mainIdx = STEPS.indexOf(status as typeof STEPS[number]);
  const isRejected = status === "REJECTED";
  const isMoreInfo = status === "MORE_INFORMATION_REQUIRED";

  return (
    <div className="bg-white border border-line rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-sm font-medium text-ink">Current:</span>
        <StatusBadge status={status} />
      </div>
      <div className="flex items-center gap-1 sm:gap-2 overflow-auto pb-2">
        {STEPS.map((s, i) => {
          const active = mainIdx >= 0 ? i <= mainIdx : false;
          const isCurrent = s === status;
          return (
            <div key={s} className="flex items-center gap-1 sm:gap-2">
              <div className={`h-7 w-7 sm:h-8 sm:w-8 rounded-full flex items-center justify-center text-xs font-mono border ${isCurrent ? "bg-ink text-paper border-ink" : active ? "bg-teal text-paper border-teal" : "bg-paper text-slate-light border-line"}`}>
                {i + 1}
              </div>
              <span className={`text-[10px] sm:text-xs whitespace-nowrap ${isCurrent ? "text-ink font-semibold" : "text-slate-light"}`}>{s.replaceAll("_", " ")}</span>
              {i < STEPS.length - 1 && <span className={`w-4 sm:w-8 h-px ${active ? "bg-teal" : "bg-line"}`} />}
            </div>
          );
        })}
      </div>
      {(isRejected || isMoreInfo) && (
        <div className="mt-3 text-xs">
          {isRejected && <span className="px-2 py-1 rounded bg-alert-soft text-alert">Rejected — terminal</span>}
          {isMoreInfo && <span className="px-2 py-1 rounded bg-amber-soft text-amber">Additional information required → customer can return to PROCESSING</span>}
        </div>
      )}
      <p className="text-xs text-slate-light mt-3">Transitions are validated by the backend state machine.</p>
    </div>
  );
}
