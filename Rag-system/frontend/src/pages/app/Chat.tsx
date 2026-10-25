import { useCallback, useEffect, useRef, useState, type ElementType, type HTMLAttributes, type KeyboardEvent } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowUp, Bot, FileText, Loader2, RotateCcw, Sparkles, Trash2 } from "lucide-react";
import { Alert, Button } from "@/components/ui";
import { useAuth } from "@/hooks/auth";
import { useProject } from "@/hooks/project";
import { useI18n } from "@/i18n";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Source {
  file_name: string;
  page: number | null;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  error?: string;
  seconds?: number;
}

interface AnswerResponse {
  signal: string;
  answer: string;
  sources: Source[];
}

const uid = () => Math.random().toString(36).slice(2, 10);

// Every block takes its direction from its own first letter, so an English
// answer inside the Arabic interface (or the opposite) is laid out correctly.
const auto = (Tag: ElementType) => ({ node: _node, ...props }: { node?: unknown } & HTMLAttributes<HTMLElement>) => <Tag {...props} dir="auto" />;

const markdownComponents = {
  p: auto("p"), ul: auto("ul"), ol: auto("ol"), li: auto("li"), blockquote: auto("blockquote"),
  h1: auto("h1"), h2: auto("h2"), h3: auto("h3"), table: auto("table"),
} as unknown as Components;

/** The conversation is kept in this browser, per user and project. */
function useStoredMessages(userId: string, projectId: number) {
  const key = `rag.chat.${userId}.${projectId}`;
  const [messages, setMessages] = useState<Message[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(key) ?? "[]") as Message[];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(messages.filter((m) => !m.error).slice(-60)));
    } catch {
      /* storage full: the conversation just is not saved */
    }
  }, [key, messages]);

  return [messages, setMessages] as const;
}

function SourceCards({ sources }: { sources: Source[] }) {
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
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AssistantMessage({ message, onRetry }: { message: Message; onRetry?: () => void }) {
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
                <RotateCcw className="size-3.5" />
                {t("common.retry")}
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

function Thinking() {
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
        <span>{t("chat.thinking")}</span>
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
  const { t, errorText } = useI18n();
  const { user } = useAuth();
  const { projectId } = useProject();
  const [messages, setMessages] = useStoredMessages(user?.id ?? "anon", projectId);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [input]);

  const ask = useCallback(
    async (question: string) => {
      const text = question.trim();
      if (!text || loading) return;

      setMessages((list) => [...list.filter((m) => !m.error), { id: uid(), role: "user", content: text }]);
      setInput("");
      setLoading(true);

      const controller = new AbortController();
      abortRef.current = controller;
      const started = Date.now();

      try {
        const result = await api<AnswerResponse>(`/api/v1/nlp/index/answer/${projectId}`, { body: { text, limit: 10 }, signal: controller.signal });

        setMessages((list) => [
          ...list,
          { id: uid(), role: "assistant", content: result.answer, sources: result.sources, seconds: Math.round((Date.now() - started) / 1000) },
        ]);
      } catch (error) {
        if ((error as Error).name === "AbortError") return;

        const message = error instanceof ApiError && error.code === "rag_answer_error" ? t("chat.noAnswer") : errorText(error);
        setMessages((list) => [...list, { id: uid(), role: "assistant", content: "", error: message }]);
      } finally {
        setLoading(false);
      }
    },
    [loading, projectId, setMessages, t, errorText],
  );

  const lastQuestion = [...messages].reverse().find((m) => m.role === "user")?.content;

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends; Shift+Enter is a new line; Arabic/Chinese composition is left alone
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void ask(input);
    }
  }

  const suggestions = [t("chat.s1"), t("chat.s2"), t("chat.s3")];

  return (
    <div className="mx-auto flex h-full w-full max-w-4xl flex-col px-4 sm:px-6">
      <div className="flex items-center justify-between py-5">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight">{t("chat.title")}</h1>
          <p className="text-[13px] text-muted">{t("chat.subtitle")}</p>
        </div>
        {messages.length > 0 && (
          <Button variant="ghost" size="sm" onClick={() => setMessages([])}>
            <Trash2 className="size-4" />
            {t("chat.clear")}
          </Button>
        )}
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 space-y-7 overflow-y-auto pb-6 pe-1">
        {messages.length === 0 && !loading ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <span className="mb-5 grid size-14 place-items-center rounded-2xl bg-primary/15 text-primary">
              <Sparkles className="size-6" />
            </span>
            <h2 className="text-2xl font-semibold tracking-tight">{t("chat.emptyTitle")}</h2>
            <p className="mt-2 max-w-md text-[14px] leading-relaxed text-muted">{t("chat.emptySub")}</p>
            <div className="mt-8 flex max-w-2xl flex-wrap justify-center gap-2.5">
              {suggestions.map((s) => (
                <button key={s} onClick={() => ask(s)} className="rounded-full border border-border bg-card px-4 py-2 text-[13px] text-foreground/85 transition-colors hover:border-primary/50 hover:bg-primary-soft hover:text-foreground">
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((message, index) =>
            message.role === "user" ? (
              <div key={message.id} className="flex justify-end animate-fade-in">
                <div dir="auto" className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-ee-md bg-primary px-4 py-3 text-[15px] leading-relaxed text-white">{message.content}</div>
              </div>
            ) : (
              <AssistantMessage key={message.id} message={message} onRetry={message.error && index === messages.length - 1 && lastQuestion ? () => ask(lastQuestion) : undefined} />
            ),
          )
        )}
        {loading && <Thinking />}
      </div>

      <div className="pb-5 pt-2">
        <div className="flex items-end gap-2 rounded-2xl border border-border bg-card p-2.5 transition-colors focus-within:border-primary/50">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder={t("chat.placeholder")}
            className="max-h-[180px] min-h-[40px] flex-1 resize-none bg-transparent px-2.5 py-2 text-[15px] placeholder:text-muted/60 focus:outline-none"
          />
          <button
            onClick={() => ask(input)}
            disabled={!input.trim() || loading}
            aria-label={t("chat.send")}
            className={cn("grid size-10 shrink-0 place-items-center rounded-xl transition-colors", input.trim() && !loading ? "bg-primary text-white hover:bg-primary/90" : "bg-elevated text-muted")}
          >
            <ArrowUp className="size-[18px]" />
          </button>
        </div>
      </div>
    </div>
  );
}
