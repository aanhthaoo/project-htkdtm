import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, tokenStore } from "../api/client.js";
import { hasRole } from "./roles.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(Boolean(tokenStore.get()));

  // Khôi phục phiên từ token đã lưu
  useEffect(() => {
    if (!tokenStore.get()) return;
    api("/api/auth/me")
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false));
  }, []);

  // Token hết hạn giữa chừng: api client phát sự kiện này
  useEffect(() => {
    const onExpired = () => setUser(null);
    window.addEventListener("auth:expired", onExpired);
    return () => window.removeEventListener("auth:expired", onExpired);
  }, []);

  const accept = useCallback((data) => {
    tokenStore.set(data.access_token);
    setUser(data.user);
    return data.user;
  }, []);

  const login = useCallback(
    async (email, password) =>
      accept(await api("/api/auth/login", { method: "POST", body: { email, password }, auth: false })),
    [accept],
  );
  const register = useCallback(
    async (email, password, full_name) =>
      accept(
        await api("/api/auth/register", { method: "POST", body: { email, password, full_name }, auth: false }),
      ),
    [accept],
  );
  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, logout, can: (minRole) => hasRole(user, minRole) }),
    [user, loading, login, register, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth phải nằm trong AuthProvider");
  return ctx;
}
