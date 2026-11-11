import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, UNAUTHORIZED_EVENT } from "./api";
import type { Role, User } from "./types";

interface AuthState {
  user: User | null;
  ready: boolean;
  login: (username: string, password: string) => Promise<User>;
  demo: (username: string) => Promise<User>;
  logout: () => Promise<void>;
  can: (...roles: Role[]) => boolean;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    api
      .me()
      .then((r) => setUser(r.user))
      .catch(() => setUser(null))
      .finally(() => setReady(true));
    const onExpired = () => setUser(null);
    window.addEventListener(UNAUTHORIZED_EVENT, onExpired);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onExpired);
  }, []);

  const login = useCallback(async (u: string, p: string) => {
    const me = await api.login(u, p);
    setUser(me);
    return me;
  }, []);
  const demo = useCallback(async (u: string) => {
    const me = await api.demoLogin(u);
    setUser(me);
    return me;
  }, []);
  const logout = useCallback(async () => {
    await api.logout().catch(() => undefined);
    setUser(null);
  }, []);
  const can = useCallback((...roles: Role[]) => !!user && (user.role === "admin" || roles.includes(user.role)), [user]);

  const value = useMemo(() => ({ user, ready, login, demo, logout, can }), [user, ready, login, demo, logout, can]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth harus di dalam AuthProvider");
  return v;
}

export const ROLE_LABEL: Record<Role, string> = {
  koperasi: "Petugas koperasi",
  pengepul: "Pengepul",
  pabrik: "Pabrik kelapa sawit",
  verifikator: "Verifikator independen",
  admin: "Admin",
};

/** Akun demo yang paling cocok untuk sebuah peran (dipakai tombol "Masuk sebagai ..."). */
export const DEMO_FOR: Record<Role, string> = {
  koperasi: "koperasi",
  pengepul: "pengepul",
  pabrik: "pabrik",
  verifikator: "verifikator",
  admin: "admin",
};
