import { useState } from "react";
import { useParams, useNavigate, Navigate } from "react-router-dom";
import { BookOpen, Brain, HelpCircle, Layers, ListChecks, NotebookPen, Sparkles, Network, MessageCircleQuestion, CheckCircle2, Languages, Square } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Page, PageHeader } from "@/components/layout/PageHeader";
import { Alert, Button, Card } from "@/components/ui";
import { useI18n } from "@/i18n";
import { useKnowledge, type KnowledgeTask } from "@/hooks/knowledge";
import { useData } from "@/hooks/data";
import { cn } from "@/lib/utils";

const TASKS: { id: KnowledgeTask; icon: any; label: string }[] = [
  { id: "summary", icon: BookOpen, label: "ملخص" },
  { id: "faq", icon: MessageCircleQuestion, label: "أسئلة شائعة" },
  { id: "mindmap", icon: Network, label: "خريطة ذهنية" },
  { id: "key-points", icon: ListChecks, label: "نقاط" },
  { id: "notes", icon: NotebookPen, label: "ملاحظات" },
  { id: "flashcards", icon: Layers, label: "بطاقات" },
  { id: "quiz", icon: Brain, label: "اختبار" },
  { id: "qa", icon: HelpCircle, label: "سؤال" },
];

export default function Knowledge() {
  const { t, lang } = useI18n();
  const { task } = useParams<{ task: KnowledgeTask }>();
  const navigate = useNavigate();
  const { query, setQuery, result, running, error, run, stop } = useKnowledge();
  const { files } = useData();
  
  const [selectedFile, setSelectedFile] = useState("");
  const [outputLang, setOutputLang] = useState<"ar" | "en">(lang);

  if (!task || !TASKS.find(t => t.id === task)) {
    return <Navigate to="/knowledge/summary" replace />;
  }

  const handleRun = () => {
    run(task, selectedFile || undefined, outputLang);
  };

  return (
    <Page wide>
      <PageHeader title={t("knowledge.title")} subtitle={t("knowledge.subtitle")} />
      
      <div className="mb-6 grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
        {TASKS.map((item) => (
          <button key={item.id} onClick={() => navigate(`/knowledge/${item.id}`)}
            className={`flex flex-col items-center gap-1.5 rounded-xl border p-3 text-xs font-medium transition-all ${
              task === item.id ? "border-primary bg-primary/10 text-primary shadow-sm scale-105" : "border-border bg-card text-foreground/80 hover:bg-elevated/60"
            }`}>
            <item.icon className="size-5" />
            {item.label}
          </button>
        ))}
      </div>

      <Card className="mb-6 p-5">
        <div className="mb-4">
          <label className="mb-1.5 block text-[13px] font-medium">مصدر البيانات (ملف أو فيديو)</label>
          <select
            value={selectedFile}
            onChange={(e) => setSelectedFile(e.target.value)}
            className="h-11 w-full rounded-xl border border-primary/40 bg-primary/5 px-3 text-sm font-medium text-primary outline-none focus:ring-2 focus:ring-primary/50"
          >
            <option value="">كل الملفات (بحث بالكلمات المفتاحية)</option>
            {files.map(f => <option key={f.file_id} value={f.file_id}>{f.name}</option>)}
          </select>
          <p className="mt-1 text-xs text-muted">لو اخترت فيديو أو ملف، النظام هيقراه بالكامل تلقائياً.</p>
        </div>
        
        {task === "qa" && (
          <div className="mt-3">
            <label className="mb-1.5 block text-[13px] font-medium">سؤالك</label>
            <textarea value={query} onChange={(e) => setQuery(e.target.value)} rows={2} placeholder="اكتب سؤالك هنا..."
              className="w-full rounded-xl border border-border bg-background/60 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50" />
          </div>
        )}
        
        <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            {running ? (
              <button onClick={stop} className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-danger/20 px-4 text-sm font-medium text-danger hover:bg-danger/30 transition-colors">
                <Square className="size-4 fill-current" /> إيقاف التحليل
              </button>
            ) : (
              <Button size="lg" disabled={task === "qa" && !query.trim() && !selectedFile} onClick={handleRun}>
                <Sparkles className="size-4" /> تنفيذ
              </Button>
            )}
            {running && <span className="text-xs text-muted animate-pulse">جاري قراءة الملف كاملاً، قد يستغرق دقائق...</span>}
          </div>

          <div className="flex items-center gap-2 rounded-lg border border-border bg-background/50 p-1">
            <span className="px-2 text-xs text-muted flex items-center gap-1"><Languages className="size-3.5"/> لغة الإجابة:</span>
            <button onClick={() => setOutputLang("ar")} className={cn("rounded-md px-3 py-1.5 text-xs font-medium transition-colors", outputLang === "ar" ? "bg-primary text-white" : "text-muted hover:bg-elevated")}>عربي</button>
            <button onClick={() => setOutputLang("en")} className={cn("rounded-md px-3 py-1.5 text-xs font-medium transition-colors", outputLang === "en" ? "bg-primary text-white" : "text-muted hover:bg-elevated")}>English</button>
          </div>
        </div>
        
        {error && <div className="mt-3"><Alert>{error}</Alert></div>}
      </Card>

      {result !== null && (
        <div className="animate-fade-in">
          {task === "summary" && <SummaryView data={result} />}
          {task === "key-points" && <KeyPointsView data={result} />}
          {task === "notes" && <NotesView data={result} />}
          {task === "faq" && <FAQView data={result} />}
          {task === "mindmap" && <MindMapView data={result} />}
          {task === "flashcards" && <FlashcardsView data={result} />}
          {task === "quiz" && <QuizView data={result} />}
          {task === "qa" && <QAView data={result} />}
        </div>
      )}
    </Page>
  );
}

/* =========================================
   المكونات المستقلة لكل شكل
   ========================================= */

function cleanJson(str: string) {
  return str.replace(/```json/g, "").replace(/```/g, "").trim();
}

function SummaryView({ data }: { data: any }) {
  return (
    <Card className="p-8 max-w-4xl mx-auto shadow-lg">
      <div className="prose-chat text-[16px] leading-loose text-foreground/90" dir="auto">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{data.summary || "لا يوجد ملخص."}</ReactMarkdown>
      </div>
      <Docs docs={data.documents} />
    </Card>
  );
}

function KeyPointsView({ data }: { data: any }) {
  const points = String(data.key_points || "").split("\n").filter(p => p.trim().length > 0);
  return (
    <Card className="p-6 max-w-3xl mx-auto">
      <h3 className="mb-4 text-lg font-bold flex items-center gap-2"><ListChecks className="text-primary"/> أهم النقاط</h3>
      <ul className="space-y-3">
        {points.map((p, i) => (
          <li key={i} className="flex items-start gap-3 rounded-lg border border-border bg-card p-3 shadow-sm">
            <CheckCircle2 className="size-5 text-success shrink-0 mt-0.5" />
            <span className="text-[15px]" dir="auto">{p.replace(/^[-*]\s*/, "")}</span>
          </li>
        ))}
      </ul>
      <Docs docs={data.documents} />
    </Card>
  );
}

function NotesView({ data }: { data: any }) {
  return (
    <Card className="p-8 max-w-4xl mx-auto bg-[url('https://www.transparenttextures.com/patterns/cream-paper.png')] border-warning/30 shadow-md">
      <h3 className="mb-4 text-lg font-bold flex items-center gap-2 text-warning"><NotebookPen /> ملاحظات مذاكرة</h3>
      <div className="prose-chat text-[15px] leading-loose border-l-4 border-warning/50 pl-4" dir="auto">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{data.notes || "لا توجد ملاحظات."}</ReactMarkdown>
      </div>
      <Docs docs={data.documents} />
    </Card>
  );
}

function FAQView({ data }: { data: any }) {
  return (
    <Card className="p-6 max-w-3xl mx-auto">
      <h3 className="mb-6 text-lg font-bold flex items-center gap-2"><MessageCircleQuestion className="text-primary"/> الأسئلة الشائعة</h3>
      <div className="space-y-4 prose-chat" dir="auto">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{data.faq || "لا توجد أسئلة."}</ReactMarkdown>
      </div>
      <Docs docs={data.documents} />
    </Card>
  );
}

function MindMapView({ data }: { data: any }) {
  return (
    <Card className="p-6 max-w-4xl mx-auto bg-slate-900 border-slate-700 shadow-xl overflow-x-auto">
      <h3 className="mb-4 text-lg font-bold flex items-center gap-2 text-slate-200"><Network className="text-blue-400"/> الخريطة الذهنية</h3>
      <div className="prose-chat text-[15px] text-slate-300 font-mono leading-relaxed" dir="auto">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{data.mindmap || "لا توجد خريطة."}</ReactMarkdown>
      </div>
      <Docs docs={data.documents} />
    </Card>
  );
}

function FlashcardsView({ data }: { data: any }) {
  let cards: any[] = [];
  try { cards = JSON.parse(cleanJson(String(data.flashcards))); } catch { }

  return (
    <Card className="p-6">
      <h3 className="mb-6 text-lg font-bold flex items-center gap-2"><Layers className="text-primary"/> بطاقات المذاكرة ({cards.length})</h3>
      {Array.isArray(cards) && cards.length > 0 ? (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {cards.map((c, i) => (
            <div key={i} className="group relative flex flex-col justify-between rounded-2xl border-2 border-primary/20 bg-gradient-to-br from-card to-background p-5 shadow-sm hover:shadow-lg hover:border-primary/50 transition-all">
              <div className="mb-4">
                <span className="inline-block rounded-full bg-primary/10 px-2.5 py-1 text-[10px] font-bold text-primary mb-2">سؤال {i + 1}</span>
                <p className="text-[15px] font-semibold text-foreground leading-snug" dir="auto">{c.front || c.question || "سؤال"}</p>
              </div>
              <div className="border-t border-border/60 pt-4 mt-auto">
                <p className="text-[14px] text-muted-foreground leading-relaxed" dir="auto">{c.back || c.answer || "إجابة"}</p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="prose-chat" dir="auto"><ReactMarkdown remarkPlugins={[remarkGfm]}>{String(data.flashcards)}</ReactMarkdown></div>
      )}
      <Docs docs={data.documents} />
    </Card>
  );
}

function QuizView({ data }: { data: any }) {
  let questions: any[] = [];
  try { questions = JSON.parse(cleanJson(String(data.quiz))); } catch { }

  return (
    <Card className="p-6 max-w-3xl mx-auto">
      <h3 className="mb-6 text-lg font-bold flex items-center gap-2"><Brain className="text-primary"/> اختبار قصير</h3>
      {Array.isArray(questions) && questions.length > 0 ? (
        <div className="space-y-8">
          {questions.map((q, i) => (
            <div key={i} className="rounded-xl border border-border bg-background/40 p-5">
              <p className="mb-4 text-[16px] font-semibold flex items-start gap-3" dir="auto">
                <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary/15 text-sm font-bold text-primary">{i + 1}</span>
                {q.question || q.q || "سؤال"}
              </p>
              <ul className="space-y-2">
                {(q.options || q.choices || []).map((opt: string, j: number) => {
                  const isCorrect = opt === (q.answer || q.correct);
                  return (
                    <li key={j} className={`flex items-center gap-3 rounded-lg border px-4 py-3 text-[14px] transition-all cursor-pointer ${
                      isCorrect ? "border-success/50 bg-success/10 text-success font-medium shadow-sm" : "border-border bg-card hover:bg-elevated/60"
                    }`} dir="auto">
                      <div className={`size-4 rounded-full border-2 flex items-center justify-center ${isCorrect ? "border-success" : "border-muted"}`}>
                        {isCorrect && <div className="size-2 rounded-full bg-success" />}
                      </div>
                      {opt}
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      ) : (
        <div className="prose-chat" dir="auto"><ReactMarkdown remarkPlugins={[remarkGfm]}>{String(data.quiz)}</ReactMarkdown></div>
      )}
      <Docs docs={data.documents} />
    </Card>
  );
}

function QAView({ data }: { data: any }) {
  return (
    <Card className="p-6 max-w-4xl mx-auto shadow-sm">
      <div className="flex gap-4">
        <div className="size-10 shrink-0 bg-primary/10 rounded-full grid place-items-center"><Sparkles className="size-5 text-primary"/></div>
        <div className="prose-chat text-[15px] leading-relaxed flex-1" dir="auto">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{data.answer || "لا توجد إجابة."}</ReactMarkdown>
        </div>
      </div>
      <Docs docs={data.documents} />
    </Card>
  );
}

function Docs({ docs }: { docs: any }) {
  if (!Array.isArray(docs) || docs.length === 0) return null;
  return (
    <div className="mt-8 border-t border-border pt-5">
      <p className="mb-3 text-[12px] font-semibold uppercase tracking-wider text-muted">المصادر المسترجعة ({docs.length})</p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {docs.slice(0, 6).map((d, i) => {
          const m = d.metadata || {};
          const name = m.original_filename || m.source || m.file_id || "مستند";
          const text = d.text || d.page_content || "";
          return (
            <div key={i} className="flex flex-col gap-2 rounded-xl border border-border bg-background/40 p-3 text-xs hover:border-primary/50 transition-colors shadow-sm">
              <div className="flex items-center gap-2">
                <span className="grid size-6 shrink-0 place-items-center rounded-lg bg-primary/15 text-[11px] font-bold text-primary">{i + 1}</span>
                <span dir="ltr" className="truncate font-medium text-foreground">{name}</span>
              </div>
              {text && <p className="line-clamp-3 text-muted text-[11px] leading-relaxed" dir="auto">{text}</p>}
            </div>
          );
        })}
      </div>
    </div>
  );
}