import { Evidence } from "../types/api";

function formatBytes(bytes?: number | null) {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString();
}

export default function EvidenceList({ evidence }: { evidence: Evidence[] }) {
  if (!evidence.length) {
    return <p className="text-sm text-slate-light">No evidence uploaded yet.</p>;
  }
  return (
    <div className="space-y-3">
      {evidence.map((ev) => (
        <div key={ev.id} className="flex items-center justify-between bg-white border border-line rounded-lg px-4 py-3">
          <div className="min-w-0">
            <div className="text-sm font-medium text-ink truncate">
              {ev.original_filename || ev.stored_filename || `Evidence #${ev.id}`}
            </div>
            <div className="text-xs text-slate-light flex flex-wrap gap-2 mt-1">
              <span className="px-1.5 py-0.5 rounded bg-paper border border-line font-mono">{ev.evidence_type}</span>
              <span>{ev.mime_type || "unknown"}</span>
              <span>· {formatBytes(ev.file_size)}</span>
              <span>· {formatDate(ev.uploaded_at)}</span>
            </div>
            {ev.description && <p className="text-xs text-slate mt-1">{ev.description}</p>}
          </div>
          <div className="text-xs text-slate-light hidden sm:block">ID {ev.id}</div>
        </div>
      ))}
    </div>
  );
}
