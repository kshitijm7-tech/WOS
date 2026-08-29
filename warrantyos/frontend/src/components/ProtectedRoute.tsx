import { Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth, Role } from "../lib/auth";

/** Wrap any route that requires a logged-in user of a specific role. Redirects to the
 * matching login page if signed out, or home if signed in as the wrong role. */
export default function ProtectedRoute({
  role,
  children,
}: {
  role: Role;
  children: ReactNode;
}) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate text-sm">
        Checking your session…
      </div>
    );
  }

  if (!user) {
    return <Navigate to={role === "customer" ? "/login" : "/admin/login"} replace />;
  }

  if (user.role !== role) {
    return <Navigate to="/" replace />;
  }

  return children;
}
