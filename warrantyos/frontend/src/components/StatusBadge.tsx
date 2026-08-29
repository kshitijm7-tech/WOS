type Tone = "neutral" | "progress" | "success" | "risk";

const TONE_STYLES: Record<Tone, string> = {
  neutral: "bg-slate-light/20 text-slate-dark",
  progress: "bg-amber-soft text-amber",
  success: "bg-teal-soft text-teal",
  risk: "bg-alert-soft text-alert",
};

const STATUS_TONE: Record<string, Tone> = {
  SUBMITTED: "neutral",
  PROCESSING: "progress",
  UNDER_REVIEW: "progress",
  MORE_INFORMATION_REQUIRED: "progress",
  APPROVED: "success",
  RESOLVED: "success",
  REJECTED: "risk",
  // legacy/future
  UNDER_VERIFICATION: "progress",
  ANALYZING: "progress",
  AI_REVIEW: "progress",
  HUMAN_REVIEW: "progress",
  REPAIR_SCHEDULED: "success",
  REPLACEMENT_PROCESSING: "success",
  REFUND_PROCESSING: "success",
  COMPLETED: "success",
  DENY: "risk",
};

export default function StatusBadge({ status }: { status: string }) {
  const tone = STATUS_TONE[status] ?? "neutral";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${TONE_STYLES[tone]}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {status.replaceAll("_", " ")}
    </span>
  );
}
