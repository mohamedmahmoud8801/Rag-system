import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

interface ProjectState {
  projectId: number;
  setProjectId: (id: number) => void;
}

const Ctx = createContext<ProjectState | null>(null);
const KEY = "rag.project_id";

// The project list API comes later; until then the project is a number (default 1).
export function ProjectProvider({ children }: { children: ReactNode }) {
  const [projectId, setId] = useState<number>(() => {
    const saved = Number(localStorage.getItem(KEY));
    return Number.isInteger(saved) && saved > 0 ? saved : 1;
  });

  const value = useMemo(
    () => ({
      projectId,
      setProjectId: (id: number) => {
        if (!Number.isInteger(id) || id < 1) return;
        localStorage.setItem(KEY, String(id));
        setId(id);
      },
    }),
    [projectId],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useProject(): ProjectState {
  const value = useContext(Ctx);
  if (!value) throw new Error("useProject must be used inside ProjectProvider");
  return value;
}
