import { createContext, useContext, useState, type ReactNode } from "react";
import { useI18n } from "@/i18n";
import { api, ApiError } from "@/lib/api";
import type { SqlQueryResponse, SqlExecuteResponse } from "@/lib/api-types";

export type QueryMode = "ask" | "sql";

interface DatabasesState {
  // Current connection being queried
  activeTargetId: string | null;
  setActiveTargetId: (id: string | null) => void;

  // Query mode
  mode: QueryMode;
  setMode: (m: QueryMode) => void;

  // Ask mode
  question: string;
  setQuestion: (q: string) => void;
  qr: SqlQueryResponse["result"] | null;
  asking: boolean;

  // Raw SQL mode
  raw: string;
  setRaw: (s: string) => void;
  er: SqlExecuteResponse["result"] | null;
  executing: boolean;

  error: string | null;
  ask: (targetId: string, provider: string, databaseUrl: string) => Promise<void>;
  exec: (targetId: string, provider: string, databaseUrl: string) => Promise<void>;
  clearResults: () => void;
}

const Ctx = createContext<DatabasesState | null>(null);

export function DatabasesProvider({ children }: { children: ReactNode }) {
  const { errorText } = useI18n();

  const [activeTargetId, setActiveTargetIdState] = useState<string | null>(null);
  const [mode, setMode] = useState<QueryMode>("ask");
  const [question, setQuestion] = useState("");
  const [raw, setRaw] = useState("SELECT * FROM ");
  const [qr, setQr] = useState<SqlQueryResponse["result"] | null>(null);
  const [er, setEr] = useState<SqlExecuteResponse["result"] | null>(null);
  const [asking, setAsking] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setActiveTargetId = (id: string | null) => {
    if (id !== activeTargetId) {
      // Switching target clears results so old data doesn't appear under new DB
      setQr(null);
      setEr(null);
      setError(null);
    }
    setActiveTargetIdState(id);
  };

  const clearResults = () => {
    setQr(null);
    setEr(null);
    setError(null);
  };

  const ask = async (_targetId: string, provider: string, databaseUrl: string) => {
    if (!question.trim() || asking) return;
    setError(null);
    setAsking(true);
    setEr(null);
    try {
      const res = await api<SqlQueryResponse>("/sql/query", {
        body: { provider, database_url: databaseUrl, question, max_rows: 100 },
      });
      setQr(res.result);
    } catch (err) {
      setError(err instanceof ApiError ? errorText(err) : String(err));
    } finally {
      setAsking(false);
    }
  };

  const exec = async (_targetId: string, provider: string, databaseUrl: string) => {
    if (!raw.trim() || executing) return;
    setError(null);
    setExecuting(true);
    setQr(null);
    try {
      const res = await api<SqlExecuteResponse>("/sql/execute", {
        body: { provider, database_url: databaseUrl, query: raw, max_rows: 100 },
      });
      setEr(res.result);
    } catch (err) {
      setError(err instanceof ApiError ? errorText(err) : String(err));
    } finally {
      setExecuting(false);
    }
  };

  return (
    <Ctx.Provider
      value={{
        activeTargetId, setActiveTargetId,
        mode, setMode,
        question, setQuestion, qr, asking,
        raw, setRaw, er, executing,
        error, ask, exec, clearResults,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useDatabases() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useDatabases must be used inside DatabasesProvider");
  return ctx;
}