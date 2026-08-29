import { Link, useNavigate } from "react-router-dom";
import { useState, FormEvent } from "react";
import AuthCard from "../components/AuthCard";
import { useAuth } from "../lib/auth";
import { ApiError } from "../lib/api";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setSubmitting(true);
    try {
      await register(fullName, email, password);
      navigate("/customer/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't reach the server. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthCard
      eyebrow="Create Account"
      title="Set up your customer account"
      footer={
        <>
          Already have an account?{" "}
          <Link to="/login" className="text-teal font-medium">
            Log in
          </Link>
        </>
      }
    >
      <form className="space-y-4" onSubmit={handleSubmit}>
        <label className="block">
          <span className="text-sm font-medium text-slate-dark">Full name</span>
          <input
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm focus:border-teal outline-none"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-slate-dark">Email</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm focus:border-teal outline-none"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-slate-dark">Password</span>
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm focus:border-teal outline-none"
          />
          <span className="text-xs text-slate-light">At least 8 characters.</span>
        </label>

        {error && (
          <p className="text-sm text-alert bg-alert-soft rounded-md px-3 py-2">{error}</p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-ink text-paper font-medium py-2.5 hover:bg-slate-dark transition disabled:opacity-60"
        >
          {submitting ? "Creating account…" : "Create account"}
        </button>
      </form>
    </AuthCard>
  );
}
