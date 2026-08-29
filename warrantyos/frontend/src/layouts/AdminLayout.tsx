import { Link, NavLink, useNavigate } from "react-router-dom";
import { ReactNode, useState } from "react";
import { useAuth } from "../lib/auth";

const nav = [
  { to: "/admin/dashboard", label: "Dashboard" },
  { to: "/admin/claims", label: "Claims Queue" },
  { to: "/admin/ai-intelligence", label: "AI Intelligence" },
];


export default function AdminLayout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  function handleLogout() {
    logout();
    navigate("/admin/login");
  }

  return (
    <div className="min-h-screen bg-paper flex">
      <aside className="hidden lg:flex w-64 bg-ink text-paper flex-col sticky top-0 h-screen">
        <div className="px-6 py-6 border-b border-slate-dark/30">
          <Link to="/" className="font-display font-semibold text-lg tracking-tight">
            Warranty<span className="text-teal">OS</span>
          </Link>
          <p className="text-xs text-slate-light mt-1 font-mono">Admin Console</p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `block px-3 py-2.5 rounded-md text-sm font-medium transition ${
                  isActive ? "bg-white/10 text-paper" : "text-slate-light hover:text-paper hover:bg-white/5"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-slate-dark/30">
          <div className="text-sm text-paper/90 truncate">{user?.full_name}</div>
          <div className="text-xs text-slate-light truncate">{user?.email} — {user?.role}</div>
          <button onClick={handleLogout} className="mt-3 w-full text-left text-sm text-slate-light hover:text-paper">
            Log out
          </button>
        </div>
      </aside>

      <div className="lg:hidden fixed top-0 left-0 right-0 z-30 bg-ink text-paper flex items-center justify-between px-4 py-3">
        <Link to="/admin/dashboard" className="font-display font-semibold">
          Warranty<span className="text-teal">OS</span>
        </Link>
        <button onClick={() => setMobileOpen(!mobileOpen)} className="p-2">
          <span className="block w-5 h-0.5 bg-paper mb-1" />
          <span className="block w-5 h-0.5 bg-paper mb-1" />
          <span className="block w-5 h-0.5 bg-paper" />
        </button>
      </div>
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-20 bg-ink pt-14">
          <nav className="px-4 py-4 space-y-1">
            {nav.map((item) => (
              <NavLink key={item.to} to={item.to} onClick={() => setMobileOpen(false)} className="block px-3 py-3 rounded-md text-paper hover:bg-white/10">
                {item.label}
              </NavLink>
            ))}
            <button onClick={handleLogout} className="block w-full text-left px-3 py-3 text-slate-light">
              Log out — {user?.email}
            </button>
          </nav>
        </div>
      )}

      <div className="flex-1 min-w-0">
        <div className="lg:hidden h-14" />
        <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">{children}</main>
      </div>
    </div>
  );
}
