import { Link } from "react-router-dom";
import { useAuth } from "../lib/auth";

export default function ComingSoon({ title, phase }: { title: string; phase: string }) {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-paper flex flex-col">
      {user && (
        <div className="flex items-center justify-between px-6 py-4 border-b border-line bg-white">
          <span className="font-display font-semibold text-sm">
            Warranty<span className="text-teal">OS</span>
          </span>
          <div className="flex items-center gap-4 text-sm">
            <span className="text-slate">
              Signed in as <span className="font-medium text-ink">{user.full_name}</span>{" "}
              <span className="text-slate-light">({user.role})</span>
            </span>
            <button onClick={logout} className="text-alert font-medium hover:underline">
              Log out
            </button>
          </div>
        </div>
      )}
      <div className="flex-1 flex items-center justify-center px-4">
        <div className="text-center max-w-sm">
          <p className="font-mono text-xs text-slate-light uppercase tracking-widest">{phase}</p>
          <h1 className="font-display font-semibold text-2xl mt-2 mb-3">{title}</h1>
          <p className="text-sm text-slate mb-6">
            This screen is wired up in a later build phase — the route, auth protection, and
            layout already exist; the working feature lands next.
          </p>
          <Link to="/" className="text-teal text-sm font-medium">
            ← Back to landing
          </Link>
        </div>
      </div>
    </div>
  );
}
