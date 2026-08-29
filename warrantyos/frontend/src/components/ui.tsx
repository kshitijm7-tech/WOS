import { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`bg-white border border-line rounded-xl shadow-card p-5 ${className}`}>{children}</div>;
}

export function Button({
  children,
  variant = "primary",
  ...props
}: { children: ReactNode; variant?: "primary" | "secondary" | "ghost" } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const base = "inline-flex items-center justify-center rounded-md px-4 py-2.5 text-sm font-medium transition disabled:opacity-60";
  const styles =
    variant === "primary"
      ? "bg-ink text-paper hover:bg-slate-dark"
      : variant === "secondary"
      ? "border border-line bg-white text-ink hover:bg-paper"
      : "text-slate hover:text-ink";
  return (
    <button className={`${base} ${styles}`} {...props}>
      {children}
    </button>
  );
}

export function Loading({ text = "Loading…" }: { text?: string }) {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="h-6 w-6 rounded-full border-2 border-line border-t-ink animate-spin" />
      <span className="ml-3 text-sm text-slate">{text}</span>
    </div>
  );
}

export function Empty({ title, body, action }: { title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="text-center py-12 bg-white border border-line rounded-xl">
      <p className="font-display font-semibold text-ink">{title}</p>
      {body && <p className="text-sm text-slate-light mt-2 max-w-md mx-auto">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="bg-alert-soft border border-alert/20 rounded-lg p-4">
      <p className="text-sm text-alert font-medium">Unable to load</p>
      <p className="text-sm text-ink mt-1">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-3 text-sm text-alert underline">
          Retry
        </button>
      )}
    </div>
  );
}
