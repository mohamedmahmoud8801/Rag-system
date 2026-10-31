import { createContext, useContext, useRef, useState, type ReactNode } from "react";
import { useProject } from "@/hooks/project";
import { useI18n } from "@/i18n";
import { api, ApiError } from "@/lib/api";

export interface GoldenItem { question: string; expected?: string; }
export interface EvalResult extends GoldenItem {
  answer: string;
  sources: { file_name: string; page: number | null }[];
  seconds: number;
  error?: string;
}

interface EvaluationState {
  items: GoldenItem[];
  results: EvalResult[];
  running: boolean;
  progress: { done: number; total: number };
  loadFile: (file: File | null) => Promise<void>;
  loadItems: (items: GoldenItem[]) => void;
  runAll: () => Promise<void>;
  reset: () => void;
}

const Ctx = createContext<EvaluationState | null>(null);

export function EvaluationProvider({ children }: { children: ReactNode }) {
  const { projectId } = useProject();
  const { errorText } = useI18n();
  const [items, setItems] = useState<GoldenItem[]>([]);
  const [results, setResults] = useState<EvalResult[]>([]);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const abortRef = useRef(false);

  const loadItems = (next: GoldenItem[]) => {
    setItems(next);
    setResults([]);
    setProgress({ done: 0, total: 0 });
  };

  const loadFile = async (file: File | null) => {
    if (!file) return;
    const text = await file.text();
    try {
      const parsed = JSON.parse(text);
      const list = Array.isArray(parsed) ? parsed : parsed.questions ?? parsed.items ?? [];
      const normalized: GoldenItem[] = list
        .map((x: Record<string, unknown>) => ({
          question: String(x.question ?? x.q ?? x.query ?? ""),
          expected: (x.expected ?? x.answer ?? x.a ?? x.ground_truth) as string | undefined,
        }))
        .filter((x: GoldenItem) => x.question);
      loadItems(normalized);
    } catch {
      loadItems([]);
    }
  };

  const runAll = async () => {
    if (!items.length || running) return;
    abortRef.current = false;
    setRunning(true);
    setResults([]);
    setProgress({ done: 0, total: items.length });

    const out: EvalResult[] = [];
    for (const item of items) {
      if (abortRef.current) break;
      const started = Date.now();
      try {
        const res = await api<{ answer: string; sources?: EvalResult["sources"] }>(
          `/api/v1/nlp/index/answer/${projectId}`,
          { body: { text: item.question, limit: 10 } },
        );
        out.push({
          ...item,
          answer: res.answer,
          sources: res.sources ?? [],
          seconds: Math.round((Date.now() - started) / 1000),
        });
      } catch (err) {
        out.push({
          ...item,
          answer: "",
          sources: [],
          seconds: Math.round((Date.now() - started) / 1000),
          error: err instanceof ApiError ? errorText(err) : String(err),
        });
      }
      setProgress({ done: out.length, total: items.length });
      setResults([...out]);
    }
    setRunning(false);
  };

  const reset = () => {
    abortRef.current = true;
    setItems([]);
    setResults([]);
    setProgress({ done: 0, total: 0 });
    setRunning(false);
  };

  return (
    <Ctx.Provider value={{ items, results, running, progress, loadFile, loadItems, runAll, reset }}>
      {children}
    </Ctx.Provider>
  );
}

export function useEvaluation() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useEvaluation must be used inside EvaluationProvider");
  return ctx;
}