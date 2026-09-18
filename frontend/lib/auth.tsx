"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import * as api from "@/lib/api";
import type { User } from "@/lib/api";

type AuthState = {
  /** null while the stored token is being checked, then the user or null. */
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  signup: (email: string, password: string, displayName: string) => Promise<User>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

/** The user behind the stored token, or null (and no token) if it is unusable. */
async function restoreSession(): Promise<User | null> {
  if (!api.getToken()) return null;
  try {
    return await api.me();
  } catch {
    api.clearToken();
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    restoreSession().then((current) => {
      if (cancelled) return;
      setUser(current);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const accept = useCallback((response: api.TokenResponse) => {
    api.setToken(response.access_token);
    setUser(response.user);
    return response.user;
  }, []);

  const login = useCallback(
    (email: string, password: string) => api.login({ email, password }).then(accept),
    [accept],
  );
  const signup = useCallback(
    (email: string, password: string, display_name: string) =>
      api.signup({ email, password, display_name }).then(accept),
    [accept],
  );
  const logout = useCallback(() => {
    api.clearToken();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, signup, logout }),
    [user, loading, login, signup, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
