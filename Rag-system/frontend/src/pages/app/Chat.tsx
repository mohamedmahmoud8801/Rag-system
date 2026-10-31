import { useEffect, useRef, useState, type ElementType, type HTMLAttributes, type KeyboardEvent } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowUp, Bot, ChevronDown, Database, Eye, FileSpreadsheet, FileText, Loader2, MessageSquarePlus, RotateCcw, Sparkles, Square } from "lucide-react";
import { Alert, Button } from "@/components/ui";
import { useI18n } from "@/i18n";
import { useChat } from "@/hooks/chat";
import { useData } from "@/hooks/data";
import { cn } from "@/lib/utils";

const auto = (Tag: ElementType) => ({ node: _node, ...props }: { node?: unknown } & HTMLAttributes<HTMLElement>) => <Tag {...props} dir="auto" />;
const markdownComponents = {
  p: auto("p"), ul: auto("ul"), ol: auto("ol"), li: auto("li"), blockquote: auto("blockquote"),
  h1: auto("h1"), h2: auto("h2"), h3: auto("h3"), table: auto("table"),
} as unknown as Components;

function SourceCards({ sources }: { sources: any[] }) {
  const { t } = useI18n();
  return (
    <div className="mt-4">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">{t("chat.sources")}</p>
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {sources.map((source, index) => (
          <div key={`${source.file_name}-${source.page}-${index}`} className="flex items-center gap-3 rounded-xl border border-border bg-background/50 px-3 py-2.5">
            <span className="grid size-6 shrink-0 place-items-center rounded-md bg-primary/15 text-[11px] font-semibold text-primary">{index + 1}</span>
            <FileText className="size-4 shrink-0 text-muted" />
            <div className="min-w-0 flex-1">
              <p dir="ltr" className="truncate text-start text-[13px] font-medium">{source.file_name}</p>
              {source.page != null && <p className="text-[11px] text-muted">{t("chat.page", { n: source.page })}</p>}
              {source.snippet && <p className="truncate text-[11px] text-primary" dir="ltr">{source.snippet}</p>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AssistantMessage({ message, onRetry }: { message: any; onRetry?: () => void }) {
  const { t } = useI18n();
  return (
    <div className="flex gap-3.5 animate-fade-in">
      <span className="mt-1 grid size-8 shrink-0 place-items-center rounded-lg border border-border bg-card text-primary">
        <Bot className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        {message.error ? (
          <Alert>
            <p>{message.error}</p>
            {onRetry && (
              <button onClick={onRetry} className="mt-1.5 inline-flex items-center gap-1.5 font-medium underline underline-offset-2">
                <RotateCcw className="size-3.5" /> {t("common.retry")}
              </button>
            )}
          </Alert>
        ) : (
          <>
            <div className="prose-chat text-[15px] text-foreground/95">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{message.content}</ReactMarkdown>
            </div>
            {message.sources && message.sources.length > 0 && <SourceCards sources={message.sources} />}
          </>
        )}
      </div>
    </div>
  );
}

function Thinking({ multimodal }: { multimodal: boolean }) {
  const { t } = useI18n();
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div className="flex items-center gap-3.5 animate-fade-in">
      <span className="grid size-8 shrink-0 place-items-center rounded-lg border border-border bg-card text-primary">
        <Loader2 className="size-4 animate-spin" />
      </span>
      <div className="flex items-center gap-2.5 text-sm text-muted">
        <span>{multimodal ? t("chat.thinkingMultimodal") : t("chat.thinking")}</span>
        <span className="flex gap-1">
          {[0, 1, 2].map((i) => (
            <span key={i} className="size-1.5 animate-pulse3 rounded-full bg-primary" style={{ animationDelay: `${i * 0.18}s` }} />
          ))}
        </span>
        <span dir="ltr" className="tabular-nums text-xs">{t("chat.elapsed", { s: seconds })}</span>
      </div>
    </div>
  );
}

export default function Chat() {
  const { t, locale } = useI18n();
  const { sessions, currentId, setCurrentId, messages, newChat, loading, mode, setMode, ask, stop, dbs, selectedDb, setSelectedDb } = useChat();
  const { files } = useData();

  const [input, setInput] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const [targetFile, setTargetFile] = useState<string>("");
  
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [input]);

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      if (input.trim() && !(mode === "database" && !selectedDb)) {
        void ask(input, targetFile || undefined);
        setInput("");
      }
    }
  }

  const lastQuestion = [...messages].reverse().find((m) => m.role === "user")?.content;
  const currentSession = sessions.find(s => s.id === currentId);

  const modes = [
    { id: "rag", label: "RAG", icon: Sparkles },
    { id: "multimodal", label: t("chat.mode.multimodal"), icon: Eye },
    { id: "excel", label: t("chat.mode.excel"), icon: FileSpreadsheet },
    { id: "database", label: t("chat.mode.database"), icon: Database },
  ] as const;

  const isSendDisabled = !input.trim() || loading || (mode === "database" && !selectedDb);

  return (
    <div className="mx-auto flex h-full w-full max-w-4xl flex-col px-4 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3 py-5">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight">{t("chat.title")}</h1>
          <p className="text-[13px] text-muted">{t("chat.subtitle")}</p>
        </div>

        <div className="flex items-center gap-2 relative">
          <button onClick={() => setShowHistory(!showHistory)} className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-1.5 text-sm font-medium outline-none hover:bg-elevated/60 transition-colors">
            <span className="max-w-[120px] truncate sm:max-w-[200px]">{currentSession?.title || "New Chat"}</span>
            <ChevronDown className="size-4 text-muted" />
          </button>

          {showHistory && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setShowHistory(false)} />
              <div className="absolute top-full end-0 mt-1 z-20 w-64 rounded-xl border border-border bg-card p-2 shadow-2xl animate-fade-in">
                <div className="mb-1 px-2 text-xs font-semibold text-muted uppercase tracking-wider">{t("chat.history")}</div>
                <div className="max-h-64 overflow-y-auto space-y-1">
                  {sessions.map(s => (
                    <button key={s.id} onClick={() => { setCurrentId(s.id); setShowHistory(false); }} className={cn("w-full text-start px-3 py-2 rounded-lg transition-colors flex flex-col", s.id === currentId ? "bg-primary/10 text-primary" : "hover:bg-elevated")}>
                      <span className="text-sm font-medium truncate">{s.title}</span>
                      <span className="text-[10px] text-muted mt-0.5" dir="ltr">{new Intl.DateTimeFormat(locale, { dateStyle: "short", timeStyle: "short" }).format(new Date(s.updated_at))}</span>
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}

          <Button variant="secondary" size="sm" onClick={newChat} className="px-2 sm:px-3">
            <MessageSquarePlus className="size-4 sm:me-1.5" />
            <span className="hidden sm:inline">{t("chat.new")}</span>
          </Button>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1.5">
          {modes.map(m => (
            <button key={m.id} onClick={() => setMode(m.id)} className={cn("inline-flex h-8 items-center gap-1.5 rounded-lg border px-2.5 text-xs font-medium transition-colors", mode === m.id ? "border-primary/50 bg-primary-soft text-primary" : "border-border text-muted hover:text-foreground")}>
              <m.icon className="size-3.5" />
              <span className="hidden sm:inline">{m.label}</span>
            </button>
          ))}
          {mode === "database" && (
            <select value={selectedDb} onChange={(e) => setSelectedDb(e.target.value)} className="h-8 max-w-[120px] truncate rounded-lg border border-border bg-card px-2 text-xs outline-none hover:bg-elevated/60 sm:max-w-[160px]">
              {dbs.length === 0 && <option value="">No databases</option>}
              {dbs.map(db => <option key={db.id} value={db.id}>{db.name}</option>)}
            </select>
          )}
        </div>

        {mode === "rag" && files.length > 0 && (
          <select 
            value={targetFile} 
            onChange={(e) => setTargetFile(e.target.value)} 
            className="h-8 max-w-[180px] sm:max-w-[250px] truncate rounded-lg border border-primary/40 bg-primary/5 px-2 text-xs font-medium text-primary outline-none hover:bg-primary/10"
          >
            <option value="">كل الملفات (شامل)</option>
            {files.map(f => <option key={f.file_id} value={f.file_id}>{f.name}</option>)}
          </select>
        )}
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 space-y-7 overflow-y-auto pb-6 pe-1">
        {messages.length === 0 && !loading ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <span className="mb-5 grid size-14 place-items-center rounded-2xl bg-primary/15 text-primary"><Sparkles className="size-6" /></span>
            <h2 className="text-2xl font-semibold tracking-tight">{t("chat.emptyTitle")}</h2>
            <p className="mt-2 max-w-md text-[14px] leading-relaxed text-muted">{t("chat.emptySub")}</p>
          </div>
        ) : (
          messages.map((message, index) =>
            message.role === "user" ? (
              <div key={message.id} className="flex justify-end animate-fade-in">
                <div dir="auto" className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-ee-md bg-primary px-4 py-3 text-[15px] leading-relaxed text-white selection:bg-white/30 selection:text-white">{message.content}</div>
              </div>
            ) : (
              <AssistantMessage key={message.id} message={message} onRetry={message.error && index === messages.length - 1 && lastQuestion ? () => ask(lastQuestion, targetFile || undefined) : undefined} />
            ),
          )
        )}
        {loading && <Thinking multimodal={mode === "multimodal"} />}
      </div>

      <div className="pb-5 pt-2">
        <div className="flex items-end gap-2 rounded-2xl border border-border bg-card p-2.5 transition-colors focus-within:border-primary/50">
          <textarea 
            ref={textareaRef} 
            value={input} 
            onChange={(e) => setInput(e.target.value)} 
            onKeyDown={onKeyDown} 
            rows={1} 
            placeholder={targetFile ? `اسأل في ${files.find(f => f.file_id === targetFile)?.name}...` : t("chat.placeholder")} 
            className="max-h-[180px] min-h-[40px] flex-1 resize-none bg-transparent px-2.5 py-2 text-[15px] placeholder:text-muted/60 focus:outline-none" 
          />
          {loading ? (
            <button onClick={stop} title={t("chat.stop")} className="grid size-10 shrink-0 place-items-center rounded-xl transition-colors bg-danger/20 text-danger hover:bg-danger/30">
              <Square className="size-[18px] fill-current" />
            </button>
          ) : (
            <button onClick={() => { ask(input, targetFile || undefined); setInput(""); }} disabled={isSendDisabled} aria-label={t("chat.send")} className={cn("grid size-10 shrink-0 place-items-center rounded-xl transition-colors", !isSendDisabled ? "bg-primary text-white hover:bg-primary/90" : "bg-elevated text-muted")}>
              <ArrowUp className="size-[18px]" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}