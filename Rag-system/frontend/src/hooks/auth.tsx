import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, refreshSession, session, type Tokens, type User } from "@/lib/api";

type Status = "loading" | "authenticated" | "anonymous";

interface AuthState {
  user: User | null;
  status: Status;
  /** call with the tokens returned by login / verify / login-with-code */
  signIn: (tokens: Tokens) => void;
  signOut: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<Status>("loading");

  // a page reload keeps the session: the refresh token gets a new access token
  useEffect(() => {
    session.onLost(() => {
      setUser(null);
      setStatus("anonymous");
    });

    let cancelled = false;

    (async () => {
      if (!session.getRefreshToken() || !(await refreshSession())) {
        session.clear();
        if (!cancelled) setStatus("anonymous");
        return;
      }

      try {
        const me = await api<{ user: User }>("/api/v1/auth/me");
        if (!cancelled) {
          setUser(me.user);
          setStatus("authenticated");
        }
      } catch {
        if (!cancelled) setStatus("anonymous");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback((tokens: Tokens) => {
    session.set(tokens);
    setUser(tokens.user);
    setStatus("authenticated");
  }, []);

  const signOut = useCallback(async () => {
    const refresh_token = session.getRefreshToken();

    if (refresh_token) {
      try {
        await api("/api/v1/auth/logout", { body: { refresh_token }, auth: false });
      } catch {
        /* the local session is closed either way */
      }
    }

    session.clear();
    setUser(null);
    setStatus("anonymous");
  }, []);

  const value = useMemo(() => ({ user, status, signIn, signOut }), [user, status, signIn, signOut]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const value = useContext(Ctx);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
