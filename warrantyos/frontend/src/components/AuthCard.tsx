import { ReactNode } from "react";
import { Link } from "react-router-dom";

export default function AuthCard({
  eyebrow,
  title,
  children,
  footer,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-paper flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <Link to="/" className="font-display font-semibold text-lg tracking-tight block text-center mb-8">
          Warranty<span className="text-teal">OS</span>
        </Link>
        <div className="bg-white border border-line rounded-xl shadow-card p-8">
          <span className="font-mono text-xs text-slate-light tracking-widest uppercase">
            {eyebrow}
          </span>
          <h1 className="font-display font-semibold text-2xl mt-2 mb-6">{title}</h1>
          {children}
        </div>
        {footer && <p className="text-center text-sm text-slate mt-6">{footer}</p>}
      </div>
    </div>
  );
}
