import { createContext, useContext, useEffect, useRef, useState, useCallback, type ReactNode } from "react";
import { useProject } from "@/hooks/project";
import { useI18n } from "@/i18n";
import { api, ApiError } from "@/lib/api";

export interface UploadedFile { file_id: string; name: string; size: number; uploaded_at: number; }
export type PipelineStep = "idle" | "upload" | "process" | "index" | "reset" | "done";

interface DataState {
  files: UploadedFile[];
  selectedFiles: string[]; // 👈 ضفنا دي
  toggleSelectFile: (id: string) => void; // 👈 ضفنا دي
  toggleSelectAll: () => void; // 👈 ضفنا دي
  upload: (fileList: FileList | null) => Promise<void>;
  addFile: (file: UploadedFile) => void;
  startPipeline: (chunkSize: number, overlap: number) => Promise<void>;
  stopPipeline: () => void;
  deleteSelected: () => Promise<void>; // 👈 ضفنا دي
  resetAll: () => Promise<void>;
  step: PipelineStep;
  summary: { files: number; chunks: number; indexed: number } | null;
  error: string | null;
  clearError: () => void;
  removeFile: (id: string) => void;
}

const Ctx = createContext<DataState | null>(null);

export function DataProvider({ children }: { children: ReactNode }) {
  const { projectId } = useProject();
  const { errorText } = useI18n();

  const FILES_KEY = `rag.files.${projectId}`;
  const EXCEL_KEY = `rag.excel.${projectId}`;

  const [files, setFiles] = useState<UploadedFile[]>(() => {
    try { return JSON.parse(localStorage.getItem(FILES_KEY) ?? "[]"); } catch { return []; }
  });

  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);

  useEffect(() => {
    try { localStorage.setItem(FILES_KEY, JSON.stringify(files)); } catch {}
  }, [files, FILES_KEY]);

  const [step, setStep] = useState<PipelineStep>("idle");
  const [summary, setSummary] = useState<{ files: number; chunks: number; indexed: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const addFile = useCallback((file: UploadedFile) => {
    setFiles((prev) => {
      if (prev.some(f => f.file_id === file.file_id)) return prev;
      return [...prev, file];
    });
  }, []);

  const removeFile = useCallback((id: string) => {
    setFiles((prev) => prev.filter((x) => x.file_id !== id));
    setSelectedFiles((prev) => prev.filter((x) => x !== id));
  }, []);

  const toggleSelectFile = useCallback((id: string) => {
    setSelectedFiles(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  }, []);

  const toggleSelectAll = useCallback(() => {
    if (selectedFiles.length === files.length) setSelectedFiles([]);
    else setSelectedFiles(files.map(f => f.file_id));
  }, [selectedFiles.length, files]);

  const upload = async (selected: FileList | null) => {
    if (!selected?.length) return;
    setError(null); setSummary(null); setStep("upload");
    try {
      const added: UploadedFile[] = [];
      for (const file of Array.from(selected)) {
        const fd = new FormData();
        fd.append("file", file);
        const res = await api<{ file_id?: string; asset_name?: string }>(`/api/v1/data/upload/${projectId}`, { body: fd });
        if (res.file_id && res.asset_name) {
          added.push({ file_id: res.asset_name, name: file.name, size: file.size, uploaded_at: Date.now() });
        }
      }
      setFiles((prev) => [...prev, ...added]);
      setStep("idle");
    } catch (err) {
      setError(err instanceof ApiError ? errorText(err) : String(err));
      setStep("idle");
    }
  };

  const startPipeline = async (chunkSize: number, overlap: number) => {
    setError(null); setSummary(null);
    abortRef.current = new AbortController();
    const signal = abortRef.current.signal;

    try {
      setStep("process");
      const proc = await api<{ processed_files?: number; inserted_chunks?: number }>(`/api/v1/data/process/${projectId}`, {
        body: { chunk_size: chunkSize, overlap_size: overlap, do_reset: 0 },
        signal,
      });
      
      setStep("index");
      const idx = await api<{ inserted_items_count?: number }>(`/api/v1/nlp/index/push/${projectId}`, {
        body: { do_reset: 0 },
        signal,
      });

      setStep("done");
      setSummary({
        files: proc.processed_files ?? 0,
        chunks: proc.inserted_chunks ?? 0,
        indexed: idx.inserted_items_count ?? 0,
      });
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        setStep("idle"); 
        return;
      }
      setError(err instanceof ApiError ? errorText(err) : String(err));
      setStep("idle");
    } finally {
      abortRef.current = null;
    }
  };

  const stopPipeline = () => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
      setStep("idle");
    }
  };

  const deleteSelected = async () => {
    if (selectedFiles.length === 0) return;
    setError(null); setSummary(null);
    try {
      await api(`/api/v1/data/delete-files/${projectId}`, {
        method: "POST",
        body: { file_ids: selectedFiles }
      });
      setFiles(prev => prev.filter(f => !selectedFiles.includes(f.file_id)));
      setSelectedFiles([]);
    } catch (err) {
      setError(err instanceof ApiError ? errorText(err) : String(err));
    }
  };

  const resetAll = async () => {
    setError(null); setSummary(null);
    try {
      setStep("reset");
      await api(`/api/v1/data/reset/${projectId}`, { method: "DELETE" });
      setFiles([]);
      setSelectedFiles([]);
      localStorage.removeItem(EXCEL_KEY);
      setStep("idle");
    } catch (err) {
      setError(err instanceof ApiError ? errorText(err) : String(err));
      setStep("idle");
    }
  };

  return (
    <Ctx.Provider value={{ files, selectedFiles, toggleSelectFile, toggleSelectAll, upload, addFile, startPipeline, stopPipeline, deleteSelected, resetAll, step, summary, error, clearError: () => setError(null), removeFile }}>
      {children}
    </Ctx.Provider>
  );
}

export function useData() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useData must be used inside DataProvider");
  return ctx;
}