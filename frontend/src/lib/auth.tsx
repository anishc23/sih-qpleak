"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getToken, setToken, type Role, type User } from "./api";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState>({
  user: null,
  loading: true,
  login: async () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password);
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

/** Redirects to /login when there is no session. */
export function useRequireAuth() {
  const { user, loading } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);
  return { user, loading };
}

export const ROLE_LABEL: Record<Role, string> = {
  SUPER_ADMIN: "Super Admin",
  QUESTION_SETTER: "Question Setter",
  REVIEWER: "Reviewer",
  EXAM_AUTHORITY: "Exam Authority",
  AUDITOR: "Auditor",
};

/**
 * Which nav entries a role sees.
 *
 * Purely cosmetic. Every one of these routes is also enforced server-side --
 * hiding a link is not access control, and the demo deliberately shows what
 * happens when you call a forbidden endpoint anyway.
 */
export const ROLE_NAV: Record<Role, string[]> = {
  SUPER_ADMIN: ["dashboard", "vault", "audit", "blockchain", "security"],
  QUESTION_SETTER: ["dashboard", "vault", "create", "audit"],
  REVIEWER: ["dashboard", "vault", "review", "variations", "audit"],
  EXAM_AUTHORITY: [
    "dashboard",
    "vault",
    "builder",
    "papers",
    "timelock",
    "audit",
    "blockchain",
    "security",
  ],
  AUDITOR: ["dashboard", "vault", "audit", "blockchain", "security"],
};
