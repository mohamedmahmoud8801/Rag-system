import { createContext, useContext, useRef, useState, type ReactNode } from "react";
import { useProject } from "@/hooks/project";
import { useI18n } from "@/i18n";
import { api, ApiError } from "@/lib/api";

export type KnowledgeTask = "qa" | "summary" | "key-points" | "notes" | "flashcards" | "quiz" | "faq" | "mindmap";

interface KnowledgeState {
  query: string;
  setQuery: (q: string) => void;
  result: unknown;
  running: boolean;
  error: string | null;
  run: (task: KnowledgeTask, fileId?: string, overrideLang?: "ar" | "en") => Promise<void>;
  stop: () => void;
}

const Ctx = createContext<KnowledgeState | null>(null);

export function KnowledgeProvider({ children }: { children: ReactNode }) {
  const { projectId } = useProject();
  const { errorText, lang } = useI18n();
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<unknown>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const abortRef = useRef<AbortController | null>(null);

  const stop = () => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
      setRunning(false);
    }
  };

  const run = async (task: KnowledgeTask, fileId?: string, overrideLang?: "ar" | "en") => {
    setRunning(true);
    setError(null);
    setResult(null);
    
    abortRef.current = new AbortController();
    const signal = abortRef.current.signal;

    try {
      const targetLang = overrideLang || lang;
      const langInstruction = targetLang === "ar" 
        ? "You MUST write your final response strictly in the Arabic language." 
        : "You MUST write your final response strictly in the English language.";
        
      const generalGuard = `\n\n[CRITICAL INSTRUCTION]: ${langInstruction} Do NOT hallucinate. Base your answer ONLY on the provided context.`;

      // 👇 مفيش limit ولا top_k في الـ body
      const res = await api<unknown>(`/api/v1/knowledge/${task}/${projectId}`, {
        body: { query: (query || "") + generalGuard, file_id: fileId },
        signal,
      });
      setResult(res);
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setError(err instanceof ApiError ? errorText(err) : String(err));
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  };

  return (
    <Ctx.Provider value={{ query, setQuery, result, running, error, run, stop }}>
      {children}
    </Ctx.Provider>
  );
}

export function useKnowledge() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useKnowledge must be used inside KnowledgeProvider");
  return ctx;
}