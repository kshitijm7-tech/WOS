import { Link, useNavigate } from "react-router-dom";
import { useState } from "react";
import type { InputHTMLAttributes } from "react";
import AuthCard from "../components/AuthCard";
import { useAuth } from "../lib/auth";
import { ApiError } from "../lib/api";

const DEMO_EMAIL = "demo.customer@warrantyos.com";
const DEMO_PASSWORD = "DemoPass123!";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleLogin(loginEmail: string, loginPassword: string) {
    setError(null);
    setSubmitting(true);
    try {
      await login(loginEmail, loginPassword);
      navigate("/customer/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't reach the server. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthCard
      eyebrow="Customer Login"
      title="Welcome back"
      footer={
        <>
          New here?{" "}
          <Link to="/register" className="text-teal font-medium">
            Create a customer account
          </Link>
        </>
      }
    >
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          handleLogin(email, password);
        }}
      >
        <Field
          label="Email"
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Field
          label="Password"
          type="password"
          placeholder="••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <div className="flex items-center justify-between text-sm">
          <label className="flex items-center gap-2 text-slate">
            <input type="checkbox" className="rounded border-line" />
            Remember me
          </label>
          <a href="#" className="text-teal">
            Forgot password?
          </a>
        </div>

        {error && (
          <p className="text-sm text-alert bg-alert-soft rounded-md px-3 py-2">{error}</p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-ink text-paper font-medium py-2.5 hover:bg-slate-dark transition disabled:opacity-60"
        >
          {submitting ? "Logging in…" : "Log in"}
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={() => handleLogin(DEMO_EMAIL, DEMO_PASSWORD)}
          className="w-full rounded-md border border-line py-2.5 text-sm font-medium text-slate hover:bg-paper transition disabled:opacity-60"
        >
          Use demo customer account
        </button>
      </form>
    </AuthCard>
  );
}

function Field({ label, ...props }: { label: string } & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-dark">{label}</span>
      <input
        className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm focus:border-teal outline-none"
        {...props}
      />
    </label>
  );
}
