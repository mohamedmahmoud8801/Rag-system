import { useRef } from "react";
import { Download, Play, Upload, X } from "lucide-react";
import { Page, PageHeader } from "@/components/layout/PageHeader";
import { Alert, Badge, Button, Card } from "@/components/ui";
import { useProject } from "@/hooks/project";
import { useI18n } from "@/i18n";
import { useEvaluation } from "@/hooks/evaluation";

export default function Evaluation() {
  const { t } = useI18n();
  const { projectId } = useProject();
  const { items, results, running, progress, loadFile, runAll, reset } = useEvaluation();
  const inputRef = useRef<HTMLInputElement>(null);

  function exportJson() {
    const blob = new Blob([JSON.stringify({ project: projectId, results }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `eval_${projectId}_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function exportCsv() {
    const rows: string[][] = [["#", "question", "expected", "answer", "seconds", "error"]];
    results.forEach((r, i) =>
      rows.push([String(i + 1), r.question, r.expected ?? "", r.answer, String(r.seconds), r.error ?? ""]),
    );
    const csv = rows.map((row) => row.map((c) => `"${(c ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `eval_${projectId}_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const avgTime = results.length ? (results.reduce((s, r) => s + r.seconds, 0) / results.length).toFixed(1) : "0";
  const failCount = results.filter((r) => r.error).length;

  return (
    <Page wide>
      <PageHeader title={t("eval.title")} subtitle={t("eval.subtitle")} />

      <Card className="mb-4 p-5">
        <div
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); loadFile(e.dataTransfer.files[0] ?? null); }}
          className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border bg-background/40 px-6 py-8 text-center hover:border-primary/50 hover:bg-primary-soft/30"
        >
          <Upload className="size-5 text-primary" />
          <p className="text-sm font-medium">{t("eval.upload")}</p>
          <p className="text-xs text-muted">{t("eval.upload.hint")}</p>
          <input
            ref={inputRef}
            type="file"
            accept=".json"
            hidden
            onChange={(e) => { loadFile(e.target.files?.[0] ?? null); e.target.value = ""; }}
          />
        </div>

        {items.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
            <Badge tone="primary">{items.length} {t("eval.items")}</Badge>
            <Button size="sm" onClick={runAll} loading={running} disabled={running}>
              <Play className="size-4" /> {t("eval.run")}
            </Button>
            <Button size="sm" variant="ghost" onClick={reset} disabled={running}>
              <X className="size-4" /> {t("eval.reset")}
            </Button>
            {results.length > 0 && (
              <>
                <Button size="sm" variant="secondary" onClick={exportJson}><Download className="size-4" /> JSON</Button>
                <Button size="sm" variant="secondary" onClick={exportCsv}><Download className="size-4" /> CSV</Button>
              </>
            )}
          </div>
        )}

        {running && (
          <div className="mt-3">
            <div className="h-2 w-full overflow-hidden rounded-full bg-border">
              <div
                className="h-full bg-primary transition-all"
                style={{ width: `${progress.total ? (progress.done / progress.total) * 100 : 0}%` }}
              />
            </div>
            <p className="mt-1.5 text-xs text-muted">{progress.done} / {progress.total}</p>
          </div>
        )}
      </Card>

      {results.length > 0 && (
        <Card className="mb-4 p-4">
          <div className="grid gap-2 text-sm sm:grid-cols-3">
            <Stat label={t("eval.stat.count")} value={String(results.length)} />
            <Stat label={t("eval.stat.avg")} value={`${avgTime}s`} />
            <Stat label={t("eval.stat.fail")} value={String(failCount)} tone={failCount ? "danger" : "success"} />
          </div>
        </Card>
      )}

      {items.length === 0 && <Alert>{t("eval.empty.hint")}</Alert>}

      <div className="space-y-3">
        {results.map((r, i) => (
          <Card key={i} className="p-4">
            <div className="mb-2 flex items-start gap-2">
              <span className="grid size-6 shrink-0 place-items-center rounded-md bg-primary/15 text-[11px] font-semibold text-primary">
                {i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold" dir="auto">{r.question}</p>
                <div className="mt-1 flex flex-wrap gap-1.5 text-[11px]">
                  <Badge>{r.seconds}s</Badge>
                  {r.error ? <Badge tone="danger">{t("eval.failed")}</Badge> : <Badge tone="success">{r.sources.length} {t("chat.sources")}</Badge>}
                </div>
              </div>
            </div>
            {r.expected && (
              <div className="mb-2 rounded-lg bg-elevated/40 p-2.5">
                <p className="mb-0.5 text-[11px] font-semibold uppercase tracking-wider text-muted">{t("eval.expected")}</p>
                <p className="text-sm" dir="auto">{r.expected}</p>
              </div>
            )}
            <div className="rounded-lg bg-background/40 p-2.5">
              <p className="mb-0.5 text-[11px] font-semibold uppercase tracking-wider text-muted">{t("eval.actual")}</p>
              {r.error
                ? <p className="text-sm text-danger" dir="auto">{r.error}</p>
                : <p className="whitespace-pre-wrap text-sm" dir="auto">{r.answer}</p>}
            </div>
            {r.sources.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {r.sources.slice(0, 6).map((s, j) => (
                  <span key={j} className="rounded-md border border-border bg-card px-2 py-0.5 text-[11px]" dir="ltr">
                    {s.file_name}{s.page ? ` · p${s.page}` : ""}
                  </span>
                ))}
              </div>
            )}
          </Card>
        ))}
      </div>
    </Page>
  );
}

function Stat({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "success" | "danger" }) {
  const color = tone === "danger" ? "text-danger" : tone === "success" ? "text-success" : "text-foreground";
  return (
    <div className="rounded-lg border border-border bg-background/40 p-3">
      <p className="text-xs text-muted">{label}</p>
      <p className={`text-lg font-semibold ${color}`}>{value}</p>
    </div>
  );
}