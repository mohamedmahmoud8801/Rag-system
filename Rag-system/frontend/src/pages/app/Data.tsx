import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  AlertTriangle, ArrowRight, CheckCircle2, Database, FileSpreadsheet, FileText,
  Info, Loader2, MessageSquare, Play, Square, Trash2, Upload,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Page, PageHeader } from "@/components/layout/PageHeader";
import { Alert, Button, Card, Input, Segmented } from "@/components/ui";
import { useProject } from "@/hooks/project";
import { useI18n } from "@/i18n";
import { api } from "@/lib/api";
import { useData } from "@/hooks/data";
import type { ExcelIngestResponse, ExcelDB } from "@/lib/api-types";

const isExcel = (n: string) => /\.(xlsx|xls)$/i.test(n);

export default function Data() {
  const { t } = useI18n();
  const [tab, setTab] = useState<"files" | "excel">("files");
  return (
    <Page wide>
      <PageHeader title={t("data.title")} subtitle={t("data.subtitle")} />
      <div className="mb-6 max-w-md">
        <Segmented value={tab} onChange={setTab} options={[
          { value: "files", label: t("data.tab.files") },
          { value: "excel", label: t("data.tab.excel") },
        ]} />
      </div>
      {tab === "files" && <FilesTab />}
      {tab === "excel" && <ExcelTab />}
    </Page>
  );
}

function FilesTab() {
  const { t } = useI18n();
  const { files, selectedFiles, toggleSelectFile, toggleSelectAll, upload, startPipeline, stopPipeline, deleteSelected, resetAll, step, summary, error, clearError } = useData();
  const inputRef = useRef<HTMLInputElement>(null);

  const [chunkSize, setChunkSize] = useState(100);
  const [overlap, setOverlap] = useState(20);
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  const isProcessing = step === "process" || step === "index";
  const busy = step === "upload" || isProcessing || step === "reset";

  const stepLabel: Record<string, string> = {
    upload: t("data.uploading"),
    process: t("data.step.process"),
    index: t("data.step.index"),
    reset: t("data.step.reset"),
    done: t("data.step.done"),
  };

  return (
    <div className="space-y-6">
      <Card className="p-5">
        <div className="mb-4 grid gap-3 sm:grid-cols-2">
          <Input label={t("data.chunkSize")} type="number" min={10} value={chunkSize} onChange={(e) => setChunkSize(+e.target.value)} ltr disabled={busy} />
          <Input label={t("data.overlapSize")} type="number" min={0} value={overlap} onChange={(e) => setOverlap(+e.target.value)} ltr disabled={busy} />
        </div>

        <div
          onClick={() => !busy && inputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); if (!busy) upload(e.dataTransfer.files); }}
          className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border bg-background/40 px-6 py-10 text-center hover:border-primary/50 hover:bg-primary-soft/30 ${busy ? "pointer-events-none opacity-60" : ""}`}
        >
          {step === "upload" ? <Loader2 className="size-6 animate-spin text-primary" /> : <Upload className="size-6 text-primary" />}
          <p className="text-sm font-medium">{step === "upload" ? t("data.uploading") : t("data.upload")}</p>
          <p className="text-xs text-muted">{t("data.upload.hint")}</p>
          <input ref={inputRef} type="file" multiple hidden onChange={(e) => { upload(e.target.files); e.target.value = ""; }} disabled={busy} />
        </div>

        {error && <div className="mt-3"><Alert>{error}</Alert><button onClick={clearError} className="text-xs text-primary mt-1 underline">Dismiss</button></div>}
      </Card>

      {files.length > 0 && (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-3">
            <div className="flex items-center gap-3">
              <input 
                type="checkbox" 
                checked={selectedFiles.length === files.length && files.length > 0} 
                onChange={toggleSelectAll}
                className="size-4 rounded border-border"
              />
              <span className="text-sm font-semibold">{t("data.files")} ({files.length})</span>
            </div>
            <div className="flex items-center gap-2">
              {selectedFiles.length > 0 && (
                <Button size="sm" variant="danger" onClick={deleteSelected}>
                  <Trash2 className="size-4" /> حذف المحدد ({selectedFiles.length})
                </Button>
              )}
              <Button size="sm" variant="danger" onClick={() => setShowResetConfirm(true)} disabled={busy}>
                <Trash2 className="size-4" /> مسح شامل
              </Button>
            </div>
          </div>
          
          <ul className="divide-y divide-border/60">
            {files.map((f) => (
              <li key={f.file_id} className="flex items-center gap-3 px-5 py-3">
                <input 
                  type="checkbox" 
                  checked={selectedFiles.includes(f.file_id)} 
                  onChange={() => toggleSelectFile(f.file_id)}
                  className="size-4 rounded border-border"
                />
                {isExcel(f.name) ? <FileSpreadsheet className="size-4 text-success" /> : <FileText className="size-4 text-primary" />}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium" dir="auto">{f.name}</p>
                  <p className="text-xs text-muted" dir="ltr">{f.file_id}</p>
                </div>
              </li>
            ))}
          </ul>

          <div className="flex flex-col items-start gap-3 border-t border-border bg-elevated/30 px-5 py-4">
            <div className="flex items-start gap-2 text-xs text-muted">
              <Info className="mt-0.5 size-3.5 shrink-0" />
              <span>اختر ملفات معينة لحذفها، أو اضغط مسح شامل لحذف كل شيء.</span>
            </div>
            
            {isProcessing ? (
              <button
                onClick={stopPipeline}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-danger/20 px-4 text-sm font-medium text-danger transition-colors hover:bg-danger/30"
              >
                <Square className="size-4 fill-current" /> {t("data.stop")} ({stepLabel[step]})
              </button>
            ) : (
              <Button onClick={() => startPipeline(chunkSize, overlap)} disabled={busy}>
                <Play className="size-4" /> {t("data.startPipeline")}
              </Button>
            )}
          </div>
        </Card>
      )}

      {summary && step === "done" && (
        <Alert tone="success">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="size-4" />
              <span>{t("data.pipeline.done", { files: summary.files, chunks: summary.chunks, indexed: summary.indexed })}</span>
            </div>
            <Link to="/chat"><Button size="sm" variant="secondary"><MessageSquare className="size-4" /> {t("data.ask")}</Button></Link>
          </div>
        </Alert>
      )}

      {showResetConfirm && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" onClick={() => !busy && setShowResetConfirm(false)}>
          <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-3 flex items-center gap-2 text-warning">
              <AlertTriangle className="size-5" />
              <h3 className="text-base font-semibold">{t("data.resetAll.title")}</h3>
            </div>
            <p className="text-sm text-muted">هيتم مسح جميع الملفات والبيانات المرتبطة بها نهائياً. هل أنت متأكد؟</p>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setShowResetConfirm(false)} disabled={busy}>{t("common.cancel")}</Button>
              <Button variant="danger" onClick={async () => { await resetAll(); setShowResetConfirm(false); }} loading={step === "reset"}>
                <Trash2 className="size-4" /> {t("data.resetAll.confirm")}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ExcelTab() {
  const { t, errorText } = useI18n();
  const { projectId } = useProject();
  const { files } = useData();
  const EXCEL_KEY = `rag.excel.${projectId}`;

  const excelFiles = files.filter((f) => isExcel(f.name));
  const [selected, setSelected] = useState(excelFiles[0]?.file_id ?? "");
  const [ifExists, setIfExists] = useState<"fail" | "replace">("replace");
  const [result, setResult] = useState<ExcelIngestResponse["result"] | null>(null);

  const ingest = useMutation({
    mutationFn: () => api<ExcelIngestResponse>("/sql/ingest", {
      body: { project_id: projectId, file_id: selected, if_exists: ifExists },
    }),
    onSuccess: (d) => {
      setResult(d.result);
      let list: ExcelDB[] = [];
      try { list = JSON.parse(localStorage.getItem(EXCEL_KEY) ?? "[]"); } catch {}
      list = list.filter((x) => x.file_id !== d.result.file_id);
      list.push({ ...d.result, ingested_at: Date.now() });
      localStorage.setItem(EXCEL_KEY, JSON.stringify(list));
    },
  });

  if (!excelFiles.length) return <Card className="p-8 text-center"><p className="text-sm text-muted">{t("data.excel.empty")}</p></Card>;

  return (
    <Card className="p-5">
      <h3 className="mb-4 text-sm font-semibold">{t("data.excel.title")}</h3>
      <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
        <select value={selected} onChange={(e) => setSelected(e.target.value)} className="h-11 rounded-xl border border-border bg-background/60 px-3 text-sm">
          {excelFiles.map((f) => <option key={f.file_id} value={f.file_id}>{f.name}</option>)}
        </select>
        <select value={ifExists} onChange={(e) => setIfExists(e.target.value as "fail" | "replace")} className="h-11 rounded-xl border border-border bg-background/60 px-3 text-sm">
          <option value="replace">{t("data.excel.replace")}</option>
          <option value="fail">{t("data.excel.fail")}</option>
        </select>
      </div>
      <div className="mt-4"><Button loading={ingest.isPending} onClick={() => ingest.mutate()}><Database className="size-4" /> {t("data.excel.run")}</Button></div>
      {ingest.error && <div className="mt-3"><Alert>{errorText(ingest.error)}</Alert></div>}
      {result && (
        <div className="mt-4 space-y-3">
          <Alert tone="success">{t("data.excel.done", { t: result.tables_created, r: result.total_rows_inserted })}</Alert>
          <div className="space-y-2">
            {result.tables.map((tb) => (
              <div key={tb.table_name} className="rounded-lg border border-border bg-background/40 p-3">
                <p className="text-sm font-medium" dir="ltr">{tb.table_name}</p>
                <p className="text-xs text-muted">{tb.inserted_rows} rows · {tb.columns.length} cols{tb.replaced ? " · replaced" : ""}</p>
              </div>
            ))}
          </div>
          <Link to="/databases" className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline">
            <ArrowRight className="size-4" /> {t("data.excel.open")}
          </Link>
        </div>
      )}
    </Card>
  );
}