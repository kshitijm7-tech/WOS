import { TimelineEvent } from "../types/api";

const TYPE_LABEL: Record<string, string> = {
  CLAIM_CREATED: "Claim submitted",
  WARRANTY_CHECKED: "Warranty checked",
  EVIDENCE_UPLOADED: "Evidence uploaded",
  STATUS_CHANGED: "Status changed",
  CLAIM_REVIEWED: "Reviewed",
  INFORMATION_REQUESTED: "Information requested",
};

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function Timeline({ events }: { events: TimelineEvent[] }) {
  if (!events.length) {
    return <p className="text-sm text-slate-light">No timeline events yet.</p>;
  }
  return (
    <div className="relative pl-6">
      <div className="absolute left-2 top-1 bottom-1 w-px bg-line" />
      <div className="space-y-5">
        {events.map((e) => (
          <div key={e.id} className="relative">
            <span className="absolute -left-5 top-1.5 h-2.5 w-2.5 rounded-full bg-teal border-2 border-white shadow" />
            <div className="bg-white border border-line rounded-lg p-3 sm:p-4">
              <div className="flex flex-wrap items-center gap-2 text-xs font-mono text-slate-light">
                <span className="px-2 py-0.5 rounded bg-paper border border-line">{TYPE_LABEL[e.event_type] ?? e.event_type}</span>
                <span>{formatDate(e.created_at)}</span>
                {e.actor && <span>· {e.actor}</span>}
              </div>
              {e.notes && <p className="text-sm text-ink mt-2">{e.notes}</p>}
              {e.event_metadata && (
                <pre className="text-xs bg-paper border border-line rounded p-2 mt-2 overflow-auto max-h-32">
                  {JSON.stringify(e.event_metadata, null, 2)}
                </pre>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
