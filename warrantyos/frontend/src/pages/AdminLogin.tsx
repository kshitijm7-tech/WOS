import { useState } from "react";
import { useNavigate } from "react-router-dom";
import AuthCard from "../components/AuthCard";
import { useAuth } from "../lib/auth";
import { ApiError } from "../lib/api";

const DEMO_EMAIL = "demo.admin@warrantyos.com";
const DEMO_PASSWORD = "DemoPass123!";

export default function AdminLogin() {
  const { login, logout } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleLogin(loginEmail: string, loginPassword: string) {
    setError(null);
    setSubmitting(true);
    try {
      const user = await login(loginEmail, loginPassword);
      if (user.role !== "admin" && user.role !== "support") {
        logout();
        setError("This account doesn't have admin access.");
        return;
      }
      navigate("/admin/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't reach the server. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthCard eyebrow="Admin Login" title="Sign in to the console">
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          handleLogin(email, password);
        }}
      >
        <label className="block">
          <span className="text-sm font-medium text-slate-dark">Email</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="admin@warrantyos.com"
            className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm focus:border-teal outline-none"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-slate-dark">Password</span>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm focus:border-teal outline-none"
          />
        </label>

        {error && (
          <p className="text-sm text-alert bg-alert-soft rounded-md px-3 py-2">{error}</p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-ink text-paper font-medium py-2.5 hover:bg-slate-dark transition disabled:opacity-60"
        >
          {submitting ? "Signing in…" : "Sign in"}
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={() => handleLogin(DEMO_EMAIL, DEMO_PASSWORD)}
          className="w-full rounded-md border border-line py-2.5 text-sm font-medium text-slate hover:bg-paper transition disabled:opacity-60"
        >
          Use demo admin account
        </button>
      </form>
    </AuthCard>
  );
}
