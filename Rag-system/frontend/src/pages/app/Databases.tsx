import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileSpreadsheet, Play, Plus, Server, Sparkles, Trash2 } from "lucide-react";
import { Page, PageHeader } from "@/components/layout/PageHeader";
import { Alert, Badge, Button, Card, Input, Segmented, Spinner } from "@/components/ui";
import { useProject } from "@/hooks/project";
import { useI18n } from "@/i18n";
import { api, ApiError } from "@/lib/api";
import { useDatabases } from "@/hooks/databases";
import type {
  DBConnection, DBListResponse, DBTestResponse, DBCreateResponse, ExcelDB,
} from "@/lib/api-types";

const loadExcelDBs = (id: number): ExcelDB[] => {
  try { return JSON.parse(localStorage.getItem(`rag.excel.${id}`) ?? "[]"); } catch { return []; }
};

type Target = { id: string; label: string; provider: string; database_url: string };

export default function Databases() {
  const { t, errorText } = useI18n();
  const { projectId } = useProject();
  const client = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const { activeTargetId, setActiveTargetId } = useDatabases();

  const conns = useQuery({
    queryKey: ["db-connections", projectId],
    queryFn: () => api<DBListResponse>(`/api/v1/databases/${projectId}`),
  });

  const excelDBs = useMemo(() => loadExcelDBs(projectId), [projectId, conns.dataUpdatedAt]);

  const del = useMutation({
    mutationFn: (id: string) => api(`/api/v1/databases/${projectId}/${id}`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["db-connections", projectId] }),
  });

  const targets: Target[] = useMemo(() => {
    const list: Target[] = [];
    for (const c of conns.data?.connections ?? []) {
      const url =
        (c.database_url as string) ||
        (typeof c.url === "string" && (c.url.startsWith("conn://") || c.url.startsWith("excel://")) ? c.url : null) ||
        `conn://${c.id}`;
      list.push({ id: `c:${c.id}`, label: c.name || c.display || c.id, provider: c.provider, database_url: url });
    }
    for (const e of excelDBs) {
      list.push({ id: `x:${e.file_id}`, label: `Excel · ${e.file_id}`, provider: "sqlite", database_url: e.database_url });
    }
    return list;
  }, [conns.data, excelDBs]);

  const active = targets.find((x) => x.id === activeTargetId) ?? targets[0];

  if (active && active.id !== activeTargetId) {
    setActiveTargetId(active.id);
  }

  return (
    <Page wide>
      <PageHeader
        title={t("db.title")}
        subtitle={t("db.subtitle")}
        actions={<Button onClick={() => setShowAdd((v) => !v)}><Plus className="size-4" /> {t("db.add")}</Button>}
      />

      {showAdd && (
        <AddConnection
          projectId={projectId}
          onDone={() => { setShowAdd(false); client.invalidateQueries({ queryKey: ["db-connections", projectId] }); }}
          onCancel={() => setShowAdd(false)}
        />
      )}

      <div className="mt-6 space-y-4">
        <Card>
          <div className="border-b border-border px-5 py-3 text-sm font-semibold">{t("db.connections")}</div>
          {conns.isLoading && <div className="p-5"><Spinner /></div>}
          {conns.error && <div className="p-5"><Alert>{errorText(conns.error)}</Alert></div>}
          {conns.data && conns.data.connections.length === 0 && <div className="p-5 text-sm text-muted">{t("db.empty")}</div>}
          {!!conns.data?.connections.length && (
            <ul className="divide-y divide-border/60">
              {conns.data.connections.map((c: DBConnection) => (
                <li key={c.id} className="flex items-center gap-3 px-5 py-3">
                  <Server className="size-4 text-primary" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{c.name}</p>
                    <p className="truncate text-xs text-muted" dir="ltr">{c.display || c.provider}</p>
                  </div>
                  <Badge>{c.provider}</Badge>
                  <Button size="sm" variant="ghost" onClick={() => del.mutate(c.id)}><Trash2 className="size-4" /></Button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {excelDBs.length > 0 && (
          <Card>
            <div className="border-b border-border px-5 py-3 text-sm font-semibold">{t("db.excelDBs")}</div>
            <ul className="divide-y divide-border/60">
              {excelDBs.map((e) => (
                <li key={e.file_id} className="flex items-center gap-3 px-5 py-3">
                  <FileSpreadsheet className="size-4 text-success" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium" dir="ltr">{e.file_id}</p>
                    <p className="text-xs text-muted">{e.tables_created} tables · {e.total_rows_inserted} rows</p>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        )}

        {targets.length > 0 && active && (
          <Card>
            <div className="flex items-center justify-between border-b border-border px-5 py-3">
              <span className="text-sm font-semibold">{t("db.query.title")}</span>
              <select
                value={active.id}
                onChange={(e) => setActiveTargetId(e.target.value)}
                className="h-9 rounded-lg border border-border bg-background/60 px-2 text-xs"
              >
                {targets.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
              </select>
            </div>
            <QueryPanel target={active} />
          </Card>
        )}
      </div>
    </Page>
  );
}

function AddConnection({ projectId, onDone, onCancel }: { projectId: number; onDone: () => void; onCancel: () => void }) {
  const { t, errorText } = useI18n();
  const [provider, setProvider] = useState<"postgresql" | "sqlite">("postgresql");
  const [name, setName] = useState("");
  const [host, setHost] = useState(""); const [port, setPort] = useState(5432);
  const [db, setDb] = useState(""); const [user, setUser] = useState("");
  const [pass, setPass] = useState(""); const [ssl, setSsl] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function test() {
    setBusy(true); setErr(null);
    try {
      const res = await api<DBTestResponse>("/api/v1/databases/test", {
        body: { provider, host, port, database: db, username: user, password: pass, ssl },
      });
      if (!res.ok) setErr(res.error || t("db.test.failed"));
    } catch (e) { setErr(e instanceof ApiError ? errorText(e) : String(e)); }
    finally { setBusy(false); }
  }

  async function save() {
    setBusy(true); setErr(null);
    try {
      if (provider === "postgresql") {
        await api<DBCreateResponse>(`/api/v1/databases/${projectId}`, {
          body: { name, provider, host, port, database: db, username: user, password: pass, ssl },
        });
      } else {
        if (!file) throw new ApiError(0, "unknown", t("db.sqlite.required"));
        const fd = new FormData();
        fd.append("name", name);
        fd.append("file", file);
        await api(`/api/v1/databases/${projectId}/sqlite-upload`, { body: fd });
      }
      onDone();
    } catch (e) { setErr(e instanceof ApiError ? errorText(e) : String(e)); }
    finally { setBusy(false); }
  }

  return (
    <Card className="mt-4 p-5">
      <h3 className="mb-4 text-sm font-semibold">{t("db.new")}</h3>
      <div className="mb-4 max-w-xs">
        <Segmented value={provider} onChange={setProvider} options={[
          { value: "postgresql", label: "PostgreSQL" },
          { value: "sqlite", label: "SQLite" },
        ]} />
      </div>
      <div className="space-y-3">
        <Input label={t("db.name")} value={name} onChange={(e) => setName(e.target.value)} />
        {provider === "postgresql" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label="Host" value={host} onChange={(e) => setHost(e.target.value)} ltr placeholder="localhost" />
            <Input label="Port" type="number" value={port} onChange={(e) => setPort(+e.target.value)} ltr />
            <Input label="Database" value={db} onChange={(e) => setDb(e.target.value)} ltr />
            <Input label="Username" value={user} onChange={(e) => setUser(e.target.value)} ltr />
            <Input label="Password" type="password" value={pass} onChange={(e) => setPass(e.target.value)} ltr />
            <label className="flex items-end gap-2 text-sm">
              <input type="checkbox" checked={ssl} onChange={(e) => setSsl(e.target.checked)} className="size-4" /> SSL
            </label>
          </div>
        ) : (
          <div>
            <label className="mb-1.5 block text-[13px] font-medium">{t("db.sqlite.file")}</label>
            <input
              type="file"
              accept=".db,.sqlite,.sqlite3"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="h-11 w-full rounded-xl border border-border bg-background/60 px-3 text-sm"
            />
          </div>
        )}
      </div>
      {err && <div className="mt-3"><Alert>{err}</Alert></div>}
      <div className="mt-4 flex items-center gap-2">
        {provider === "postgresql" && <Button variant="secondary" onClick={test} loading={busy}>{t("db.test.run")}</Button>}
        <Button
          onClick={save}
          loading={busy}
          disabled={!name || (provider === "sqlite" && !file) || (provider === "postgresql" && (!host || !db))}
        >
          {t("db.save")}
        </Button>
        <Button variant="ghost" onClick={onCancel}>{t("common.cancel")}</Button>
      </div>
    </Card>
  );
}

function QueryPanel({ target }: { target: Target }) {
  const { t } = useI18n();
  const {
    mode, setMode, question, setQuestion, qr, asking,
    raw, setRaw, er, executing, error, ask, exec,
  } = useDatabases();

  // 👇 State الخاصة بالتقييم
  const [evalResult, setEvalResult] = useState<any>(null);
  const [evaluating, setEvaluating] = useState(false);

  const handleEvaluate = async () => {
    if (!question || !qr?.sql) return;
    setEvaluating(true);
    try {
      const resData = JSON.stringify(qr.result?.rows || []);
      const res = await api<any>(`/sql/evaluate`, {
        body: { question, sql_query: qr.sql, result_data: resData }
      });
      setEvalResult(res);
    } catch (e) {
      console.error(e);
    } finally {
      setEvaluating(false);
    }
  };

  return (
    <div className="space-y-4 p-5">
      <div className="max-w-xs">
        <Segmented value={mode} onChange={setMode} options={[
          { value: "ask", label: t("db.mode.ask") },
          { value: "sql", label: t("db.mode.sql") },
        ]} />
      </div>

      {mode === "ask" ? (
        <form
          onSubmit={(e) => { e.preventDefault(); if (question.trim()) ask(target.id, target.provider, target.database_url); }}
          className="space-y-3"
        >
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={2}
            placeholder={t("db.ask.placeholder")}
            className="w-full rounded-xl border border-border bg-background/60 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
          <Button type="submit" loading={asking} disabled={!question.trim()}>
            <Sparkles className="size-4" /> {t("db.ask.run")}
          </Button>
        </form>
      ) : (
        <form
          onSubmit={(e) => { e.preventDefault(); if (raw.trim()) exec(target.id, target.provider, target.database_url); }}
          className="space-y-3"
        >
          <textarea
            value={raw}
            onChange={(e) => setRaw(e.target.value)}
            rows={4}
            dir="ltr"
            className="w-full rounded-xl border border-border bg-background/60 px-3 py-2.5 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
          <Button type="submit" loading={executing} disabled={!raw.trim()}>
            <Play className="size-4" /> {t("db.sql.run")}
          </Button>
        </form>
      )}

      {error && <Alert>{error}</Alert>}

      {qr && (
        <div className="space-y-3">
          <div className="rounded-lg border border-border bg-background/40 p-3">
            <p className="mb-1 text-xs font-semibold text-muted">{t("db.sql.used")}</p>
            <pre dir="ltr" className="overflow-auto text-xs">{qr.sql}</pre>
          </div>
          {qr.warning && <Alert>{qr.warning}</Alert>}
          <ResultsTable columns={qr.result.columns} rows={qr.result.rows} />
          
          {/* 👇 زرار التقييم بيظهر هنا تحت النتيجة */}
          <div className="mt-4 flex items-center gap-3 border-t border-border/50 pt-4">
            {!evalResult ? (
              <button onClick={handleEvaluate} disabled={evaluating || !question} className="text-[13px] font-medium text-primary hover:underline flex items-center gap-1.5 disabled:opacity-50">
                {evaluating ? "جاري التقييم..." : "تقييم دقة الاستعلام"}
              </button>
            ) : (
              <div className="flex flex-wrap items-center gap-3 rounded-lg bg-elevated/40 p-2 px-3 text-[12px] animate-fade-in border border-border">
                <span className="font-semibold text-foreground">التقييم:</span>
                <span className="flex items-center gap-1">الدقة <strong className={evalResult.score >= 70 ? "text-success" : "text-danger"}>{evalResult.score}%</strong></span>
                <span className="text-muted max-w-[250px] truncate" title={evalResult.reason}>{evalResult.reason}</span>
              </div>
            )}
          </div>
        </div>
      )}
      {er && <ResultsTable columns={er.columns} rows={er.rows} />}
    </div>
  );
}

function ResultsTable({ columns, rows }: { columns?: string[]; rows?: Record<string, unknown>[] }) {
  const { t } = useI18n();
  if (!rows?.length) return <p className="text-sm text-muted">{t("db.result.empty")}</p>;
  const cols = columns && columns.length ? columns : Object.keys(rows[0]);
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full min-w-[400px] text-sm">
        <thead>
          <tr className="border-b border-border bg-elevated/40">
            {cols.map((c) => <th key={c} className="px-3 py-2 text-start font-medium" dir="ltr">{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 200).map((row, i) => (
            <tr key={i} className="border-b border-border/60 last:border-0">
              {cols.map((c) => (
                <td key={c} className="px-3 py-2 text-xs" dir="ltr">
                  {typeof row[c] === "object" ? JSON.stringify(row[c]) : String(row[c] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 200 && <p className="p-2 text-xs text-muted">200 / {rows.length}</p>}
    </div>
  );
}