import { createContext, useContext, useState, type ReactNode } from "react";
import { useProject } from "@/hooks/project";
import { useI18n } from "@/i18n";
import { api, ApiError } from "@/lib/api";
import type { VideoIngestResponse } from "@/lib/api-types";

interface VideoState {
  url: string;
  setUrl: (v: string) => void;
  language: string;
  setLanguage: (v: string) => void;
  chunkSize: number;
  setChunkSize: (v: number) => void;
  overlap: number;
  setOverlap: (v: number) => void;
  result: VideoIngestResponse | null;
  loading: boolean;
  error: string | null;
  ingest: () => Promise<void>;
  clear: () => void;
}

const Ctx = createContext<VideoState | null>(null);

export function VideoProvider({ children }: { children: ReactNode }) {
  const { projectId } = useProject();
  const { errorText } = useI18n();
  const [url, setUrl] = useState("");
  const [language, setLanguage] = useState("");
  const [chunkSize, setChunkSize] = useState(1200);
  const [overlap, setOverlap] = useState(200);
  const [result, setResult] = useState<VideoIngestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ingest = async () => {
    if (!url.trim() || loading) return;
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const res = await api<VideoIngestResponse>(`/api/v1/video/ingest/${projectId}`, {
        body: {
          video_url: url,
          provider: "youtube",
          language: language || null,
          chunk_size: chunkSize,
          chunk_overlap: overlap,
        },
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? errorText(err) : String(err));
    } finally {
      setLoading(false);
    }
  };

  const clear = () => {
    setUrl("");
    setLanguage("");
    setResult(null);
    setError(null);
  };

  return (
    <Ctx.Provider value={{ url, setUrl, language, setLanguage, chunkSize, setChunkSize, overlap, setOverlap, result, loading, error, ingest, clear }}>
      {children}
    </Ctx.Provider>
  );
}

export function useVideo() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useVideo must be used inside VideoProvider");
  return ctx;
}