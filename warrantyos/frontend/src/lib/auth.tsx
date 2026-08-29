import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { api, setAuthToken } from "./api";

export type Role = "customer" | "admin" | "support";

export interface AuthUser {
  id: number;
  email: string;
  full_name: string;
  role: Role;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<AuthUser>;
  register: (fullName: string, email: string, password: string) => Promise<AuthUser>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const TOKEN_KEY = "warrantyos_token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // On first load, if a token was saved from a previous session, validate it against
  // /auth/me rather than trusting it blindly — it may have expired or been revoked.
  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (!stored) {
      setLoading(false);
      return;
    }
    setAuthToken(stored);
    api
      .get<AuthUser>("/auth/me")
      .then(setUser)
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        setAuthToken(null);
      })
      .finally(() => setLoading(false));
  }, []);

  function applySession(res: TokenResponse) {
    localStorage.setItem(TOKEN_KEY, res.access_token);
    setAuthToken(res.access_token);
    setUser(res.user);
    return res.user;
  }

  async function login(email: string, password: string) {
    const res = await api.post<TokenResponse>("/auth/login", { email, password });
    return applySession(res);
  }

  async function register(full_name: string, email: string, password: string) {
    const res = await api.post<TokenResponse>("/auth/register", { full_name, email, password });
    return applySession(res);
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setAuthToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
