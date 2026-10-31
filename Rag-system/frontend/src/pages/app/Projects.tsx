import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, FileSpreadsheet, FileText, FolderOpen, MessageSquare, Plus, Trash2 } from "lucide-react";
import { Page, PageHeader } from "@/components/layout/PageHeader";
import { Alert, Badge, Button, Card, Input } from "@/components/ui";
import { useProject } from "@/hooks/project";
import { useI18n } from "@/i18n";

interface LocalProject { id: number; name: string; created_at: number; }
const KEY = "rag.projects.list";

const loadProjects = (): LocalProject[] => { try { return JSON.parse(localStorage.getItem(KEY) ?? "[]"); } catch { return []; } };
const saveProjects = (list: LocalProject[]) => localStorage.setItem(KEY, JSON.stringify(list));

const fileCount = (id: number): number => {
  try { const f = JSON.parse(localStorage.getItem(`rag.files.${id}`) ?? "[]"); return Array.isArray(f) ? f.length : 0; } catch { return 0; }
};
const excelCount = (id: number): number => {
  try { const d = JSON.parse(localStorage.getItem(`rag.excel.${id}`) ?? "[]"); return Array.isArray(d) ? d.length : 0; } catch { return 0; }
};

const clearProjectData = (id: number) => {
  localStorage.removeItem(`rag.files.${id}`);
  localStorage.removeItem(`rag.excel.${id}`);
  for (let i = localStorage.length - 1; i >= 0; i--) {
    const k = localStorage.key(i);
    if (k && k.startsWith("rag.chat.") && k.endsWith(`.${id}`)) localStorage.removeItem(k);
  }
};

export default function Projects() {
  const { t } = useI18n();
  const { projectId, setProjectId } = useProject();
  const [projects, setProjects] = useState<LocalProject[]>(() => loadProjects());
  const [newId, setNewId] = useState("");
  const [newName, setNewName] = useState("");
  const [confirm, setConfirm] = useState<number | null>(null);

  useEffect(() => {
    if (projects.some((p) => p.id === projectId)) return;
    const next = [...projects, { id: projectId, name: `Project #${projectId}`, created_at: Date.now() }].sort((a, b) => a.id - b.id);
    setProjects(next);
    saveProjects(next);
  }, [projectId, projects]);

  const current = useMemo(() => projects.find((p) => p.id === projectId), [projects, projectId]);

  function addProject() {
    const id = Number(newId);
    if (!Number.isInteger(id) || id < 1) return;
    if (projects.some((p) => p.id === id)) { setProjectId(id); setNewId(""); setNewName(""); return; }
    const next = [...projects, { id, name: newName.trim() || `Project #${id}`, created_at: Date.now() }].sort((a, b) => a.id - b.id);
    saveProjects(next); setProjects(next); setProjectId(id);
    setNewId(""); setNewName("");
  }

  function removeProject(id: number) {
    clearProjectData(id);
    const next = projects.filter((p) => p.id !== id);
    saveProjects(next); setProjects(next); setConfirm(null);
    if (id === projectId) setProjectId(next[0]?.id ?? 1);
  }

  return (
    <Page>
      <PageHeader title={t("projects.title")} subtitle={t("projects.subtitle")} />

      <Card className="mb-4 p-5">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold">{t("projects.current")}</h3>
          <Badge tone="primary">#{projectId}</Badge>
        </div>
        <p className="text-sm text-muted">{current?.name ?? `Project #${projectId}`}</p>
        <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted">
          <span className="inline-flex items-center gap-1.5"><FileText className="size-3.5" /> {fileCount(projectId)} {t("projects.files")}</span>
          <span className="inline-flex items-center gap-1.5"><FileSpreadsheet className="size-3.5" /> {excelCount(projectId)} {t("projects.excel")}</span>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link to="/chat"><Button size="sm"><MessageSquare className="size-4" /> {t("projects.ask")}</Button></Link>
          <Link to="/data"><Button size="sm" variant="secondary"><FolderOpen className="size-4" /> {t("projects.manage")}</Button></Link>
        </div>
      </Card>

      <Card className="mb-4 p-5">
        <h3 className="mb-3 text-sm font-semibold">{t("projects.add")}</h3>
        <div className="grid gap-3 sm:grid-cols-[120px_1fr_auto]">
          <Input label={t("projects.id")} type="number" min={1} value={newId} onChange={(e) => setNewId(e.target.value)} ltr placeholder="1" />
          <Input label={t("projects.name")} value={newName} onChange={(e) => setNewName(e.target.value)} placeholder={t("projects.name.ph")} />
          <div className="flex items-end"><Button onClick={addProject} disabled={!newId}><Plus className="size-4" /> {t("projects.add.btn")}</Button></div>
        </div>
      </Card>

      {projects.length > 0 && (
        <Card>
          <div className="border-b border-border px-5 py-3 text-sm font-semibold">{t("projects.list")}</div>
          <ul className="divide-y divide-border/60">
            {projects.map((p) => (
              <li key={p.id} className="flex items-center gap-3 px-5 py-3">
                <span className="grid size-8 place-items-center rounded-lg bg-primary/15 text-xs font-semibold text-primary">#{p.id}</span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{p.name}</p>
                  <p className="text-xs text-muted">{fileCount(p.id)} {t("projects.files")} · {excelCount(p.id)} {t("projects.excel")}</p>
                </div>
                {p.id === projectId ? (
                  <Badge tone="success">{t("projects.active")}</Badge>
                ) : (
                  <Button size="sm" variant="secondary" onClick={() => setProjectId(p.id)}>
                    <ArrowRight className="size-4 rtl:-scale-x-100" /> {t("projects.switch")}
                  </Button>
                )}
                <Button size="sm" variant="ghost" onClick={() => setConfirm(p.id)}><Trash2 className="size-4" /></Button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {confirm !== null && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" onClick={() => setConfirm(null)}>
          <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-base font-semibold">{t("projects.delete.title")}</h3>
            <p className="mt-2 text-sm text-muted">{t("projects.delete.warning", { id: confirm })}</p>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setConfirm(null)}>{t("common.cancel")}</Button>
              <Button variant="danger" onClick={() => removeProject(confirm)}><Trash2 className="size-4" /> {t("projects.delete.confirm")}</Button>
            </div>
          </div>
        </div>
      )}

      <div className="mt-4"><Alert>{t("projects.notice")}</Alert></div>
    </Page>
  );
}