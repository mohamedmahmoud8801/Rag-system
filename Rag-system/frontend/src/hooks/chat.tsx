import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/hooks/auth";
import { useProject } from "@/hooks/project";
import { useI18n } from "@/i18n";
import type { SqlQueryResponse, DBListResponse } from "@/lib/api-types";

export interface Source {
  file_name: string;
  page: number | null;
  snippet?: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  error?: string;
  seconds?: number;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  updated_at: number;
}

export type ChatMode = "rag" | "multimodal" | "excel" | "database";

interface ChatState {
  sessions: ChatSession[];
  currentId: string;
  setCurrentId: (id: string) => void;
  messages: Message[];
  setMessages: (updater: Message[] | ((prev: Message[]) => Message[])) => void;
  newChat: () => void;
  loading: boolean;
  mode: ChatMode;
  setMode: (mode: ChatMode) => void;
  ask: (question: string, fileId?: string) => Promise<void>;
  stop: () => void;
  dbs: any[];
  selectedDb: string;
  setSelectedDb: (id: string) => void;
}

const Ctx = createContext<ChatState | null>(null);
const uid = () => Math.random().toString(36).slice(2, 10);

const cleanText = (text: string) => {
  if (!text) return text;
  return text.replace(/[\u4e00-\u9fa5\u3040-\u30ff\uac00-\ud7af]+/g, "");
};

export function ChatProvider({ children }: { children: ReactNode }) {
  const { user, status } = useAuth();
  const { projectId } = useProject();
  const { t, errorText } = useI18n();
  const userId = user?.id ?? "anon";

  const SESSIONS_KEY = `rag.sessions.${userId}.${projectId}`;
  const CURRENT_KEY = `rag.current.${userId}.${projectId}`;
  const MODE_KEY = "rag.chat.mode";

  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentId, setCurrentId] = useState<string>("");
  const [mode, setMode] = useState<ChatMode>(() => {
    const saved = localStorage.getItem(MODE_KEY);
    return (saved as ChatMode) || "rag";
  });

  const [dbs, setDbs] = useState<any[]>([]);
  const [selectedDb, setSelectedDb] = useState<string>("");
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (status === "loading") return;
    try {
      const saved = JSON.parse(localStorage.getItem(SESSIONS_KEY) ?? "[]") as ChatSession[];
      if (saved.length > 0) {
        setSessions(saved);
        const savedCur = localStorage.getItem(CURRENT_KEY);
        if (savedCur && saved.some(s => s.id === savedCur)) {
          setCurrentId(savedCur);
        } else {
          setCurrentId(saved[0].id);
        }
      } else {
        const n = { id: uid(), title: "New Chat", messages: [], updated_at: Date.now() };
        setSessions([n]);
        setCurrentId(n.id);
      }
    } catch { /* ignore */ }
  }, [SESSIONS_KEY, CURRENT_KEY, status]);

  useEffect(() => {
    if (status === "loading" || sessions.length === 0) return;
    try { localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions)); } catch {}
  }, [sessions, SESSIONS_KEY, status]);

  useEffect(() => {
    if (status === "loading" || !currentId) return;
    localStorage.setItem(CURRENT_KEY, currentId);
  }, [currentId, CURRENT_KEY, status]);

  useEffect(() => {
    localStorage.setItem(MODE_KEY, mode);
  }, [mode]);

  useEffect(() => {
    if (mode === "database") {
      api<DBListResponse>(`/api/v1/databases/${projectId}`).then(res => {
        const conns = res.connections || [];
        setDbs(conns);
        // 👇 ضفنا String() هنا
        if (conns.length > 0 && !selectedDb) setSelectedDb(String(conns[0].id));
      }).catch(() => {});
    }
  }, [mode, projectId, selectedDb]);

  const current = sessions.find((s) => s.id === currentId) || sessions[0];
  const messages = current?.messages || [];
  const loading = loadingId === currentId;

  const setMessages = useCallback((updater: Message[] | ((prev: Message[]) => Message[])) => {
    setSessions((prev) => prev.map((s) => {
      if (s.id !== currentId) return s;
      const newMsgs = typeof updater === "function" ? updater(s.messages) : updater;
      let title = s.title;
      if (title === "New Chat" && newMsgs.length > 0) {
        const firstUser = newMsgs.find((m) => m.role === "user");
        if (firstUser) title = firstUser.content.slice(0, 30) + (firstUser.content.length > 30 ? "..." : "");
      }
      return { ...s, messages: newMsgs, title, updated_at: Date.now() };
    }));
  }, [currentId]);

  const newChat = useCallback(() => {
    const newSession = { id: uid(), title: "New Chat", messages: [], updated_at: Date.now() };
    setSessions((prev) => [newSession, ...prev]);
    setCurrentId(newSession.id);
  }, []);

  const stop = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
      setLoadingId(null);
    }
  }, []);

  const ask = useCallback(async (question: string, fileId?: string) => {
    const text = question.trim();
    if (!text || loadingId) return;

    const chatId = currentId;
    setMessages((list) => [...list.filter((m) => !m.error), { id: uid(), role: "user", content: text }]);
    setLoadingId(chatId);

    abortRef.current = new AbortController();
    const signal = abortRef.current.signal;
    const started = Date.now();

    try {
      const generalGuard = `
\n\n[CRITICAL SYSTEM INSTRUCTIONS]:
1. Language: You MUST reply strictly in the exact same language as the user's question. Do not mix languages.
2. Document Parsing: The provided context may contain text extracted via OCR or PDF parsing. This text may have disconnected Arabic letters, reversed numbers, or flattened 2D tables. You must mentally reconstruct and normalize the text to understand its true meaning.
3. STRICT ADHERENCE: Base your answer ONLY on the provided context. DO NOT add external legal conclusions, inferences, or articles that are not explicitly written in the context. 
4. Silent Correction: If the text has spelling errors (e.g., 'آن' instead of 'أن'), fix them silently in your answer without changing the legal meaning.
5. Accuracy & Anti-Hallucination: Do not guess. If the requested information is genuinely not in the provided context, state clearly that you cannot find it in the documents.
6. Professionalism: Act as an expert assistant. Be concise, direct, and highly accurate.
      `;

      if (mode === "multimodal") {
        const result = await api<any>(`/api/v1/nlp/index/multimodal-answer/${projectId}`, {
          body: { text: text + generalGuard, limit: 20, file_id: fileId },
          signal,
        });

        const seen = new Set<string>();
        const sources: Source[] = [];
        for (const d of result.documents ?? []) {
          const fileName = (d.metadata?.original_filename as string) || (d.metadata?.source as string) || d.file_id;
          const page = d.page ?? (d.metadata?.page as number | undefined) ?? null;
          if (!fileName) continue;
          const key = `${fileName}|${page}`;
          if (seen.has(key)) continue;
          seen.add(key);
          const vlm = d.vlm_analysis;
          const snippet = vlm?.found && vlm.position ? [vlm.position, vlm.landmark].filter(Boolean).join(" · ") : undefined;
          sources.push({ file_name: fileName, page, snippet });
        }

        setSessions((prev) => prev.map(s => s.id === chatId ? { ...s, messages: [...s.messages, { id: uid(), role: "assistant", content: cleanText(result.answer), sources, seconds: Math.round((Date.now() - started) / 1000) }] } : s));
      } else if (mode === "excel" || mode === "database") {
        let db_url = "";
        let db_provider = "";
        if (mode === "excel") {
          db_url = `excel://${projectId}`;
          db_provider = "sqlite";
        } else {
          const conn = dbs.find(d => String(d.id) === String(selectedDb)); // 👇 ضفنا String() هنا كمان
          if (!conn) throw new Error("Please select a database connection first.");
          db_url = conn.database_url || conn.url || `conn://${conn.id}`;
          db_provider = conn.provider;
        }

        const res = await api<SqlQueryResponse>("/sql/query", {
          body: { question: text, database_url: db_url, provider: db_provider, max_rows: 100 },
          signal,
        });

        const sqlData = res.result;
        let answer = `**Generated SQL:**\n\`\`\`sql\n${sqlData.sql}\n\`\`\`\n\n`;
        const cols = sqlData.result?.columns || [];
        const rows = sqlData.result?.rows || [];
        if (rows.length === 0) {
          answer += "No results returned.";
        } else {
          answer += `| ${cols.join(" | ")} |\n| ${cols.map(() => "---").join(" | ")} |\n`;
          for (const row of rows.slice(0, 50)) {
            answer += `| ${cols.map(c => String(row[c] ?? "")).join(" | ")} |\n`;
          }
          if (rows.length > 50) answer += `\n*Showing 50 of ${rows.length} rows*`;
        }
        setSessions((prev) => prev.map(s => s.id === chatId ? { ...s, messages: [...s.messages, { id: uid(), role: "assistant", content: cleanText(answer), seconds: Math.round((Date.now() - started) / 1000) }] } : s));
      } else {
        const result = await api<any>(`/api/v1/nlp/index/answer/${projectId}`, {
          body: { text: text + generalGuard, limit: 20, file_id: fileId },
          signal,
        });
        setSessions((prev) => prev.map(s => s.id === chatId ? { ...s, messages: [...s.messages, { id: uid(), role: "assistant", content: cleanText(result.answer), sources: result.sources, seconds: Math.round((Date.now() - started) / 1000) }] } : s));
      }
    } catch (error) {
      if ((error as Error).name === "AbortError") return;
      const message = error instanceof ApiError && error.code === "rag_answer_error" ? t("chat.noAnswer") : errorText(error);
      setSessions((prev) => prev.map(s => s.id === chatId ? { ...s, messages: [...s.messages, { id: uid(), role: "assistant", content: "", error: message }] } : s));
    } finally {
      const elapsed = Date.now() - started;
      if (elapsed < 800) await new Promise((r) => setTimeout(r, 800 - elapsed));
      setLoadingId(null);
      abortRef.current = null;
    }
  }, [currentId, loadingId, mode, projectId, setMessages, t, errorText, dbs, selectedDb]);

  const value = {
    sessions, currentId, setCurrentId, messages, setMessages, newChat, loading, mode, setMode, ask, stop, dbs, selectedDb, setSelectedDb
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useChat() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useChat must be used inside ChatProvider");
  return ctx;
}