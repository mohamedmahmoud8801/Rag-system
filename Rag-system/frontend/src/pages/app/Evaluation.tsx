import { useEffect, useState } from "react";
import { Activity, Target, Database, ShieldAlert, BarChart3, Trash2, CheckCircle2, AlertCircle } from "lucide-react";
import { Page, PageHeader } from "@/components/layout/PageHeader";
import { Badge, Button, Card } from "@/components/ui";

interface EvalRecord {
  question: string;
  answer: string;
  type: "rag" | "sql";
  faithfulness?: number;
  relevance?: number;
  score?: number;
  reason: string;
  date: number;
}

export default function Evaluation() {
  const [history, setHistory] = useState<EvalRecord[]>([]);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("rag.eval_history") || "[]");
      setHistory(saved);
    } catch { }
  }, []);

  const clearHistory = () => {
    localStorage.removeItem("rag.eval_history");
    setHistory([]);
  };

  const ragResults = history.filter(r => r.type === "rag" && r.faithfulness !== undefined && r.relevance !== undefined);
  const sqlResults = history.filter(r => r.type === "sql" && r.score !== undefined);

  const avgFaith = ragResults.length ? (ragResults.reduce((a, b) => a + (b.faithfulness || 0), 0) / ragResults.length).toFixed(1) : "0";
  const avgRel = ragResults.length ? (ragResults.reduce((a, b) => a + (b.relevance || 0), 0) / ragResults.length).toFixed(1) : "0";
  const avgSql = sqlResults.length ? (sqlResults.reduce((a, b) => a + (b.score || 0), 0) / sqlResults.length).toFixed(1) : "0";

  return (
    <Page wide>
      <PageHeader 
        title="لوحة تقييم النظام (Dashboard)" 
        subtitle="نظرة عامة على أداء الـ RAG والـ SQL بناءً على تقييماتك في المحادثة."
        actions={
          history.length > 0 && (
            <Button variant="danger" size="sm" onClick={clearHistory}>
              <Trash2 className="size-4" /> مسح السجل
            </Button>
          )
        }
      />

      {/* كروت الإحصائيات */}
      <div className="grid gap-4 sm:grid-cols-3 mb-8">
        <Card className="p-6 bg-gradient-to-br from-card to-background border-success/30 shadow-sm relative overflow-hidden">
          <div className="absolute top-0 right-0 p-4 opacity-10"><ShieldAlert className="size-20" /></div>
          <div className="flex items-center gap-3 mb-2 relative z-10">
            <span className="grid size-10 place-items-center rounded-xl bg-success/15 text-success"><ShieldAlert className="size-5" /></span>
            <h3 className="text-sm font-semibold">أمانة الـ RAG (Faithfulness)</h3>
          </div>
          <p className="text-4xl font-bold relative z-10">{avgFaith}%</p>
          <p className="text-xs text-muted mt-2 relative z-10">متوسط التزام الموديل بالنصوص المسترجعة (بدون هلوسة).</p>
        </Card>
        
        <Card className="p-6 bg-gradient-to-br from-card to-background border-primary/30 shadow-sm relative overflow-hidden">
          <div className="absolute top-0 right-0 p-4 opacity-10"><Target className="size-20" /></div>
          <div className="flex items-center gap-3 mb-2 relative z-10">
            <span className="grid size-10 place-items-center rounded-xl bg-primary/15 text-primary"><Target className="size-5" /></span>
            <h3 className="text-sm font-semibold">ملاءمة الـ RAG (Relevance)</h3>
          </div>
          <p className="text-4xl font-bold relative z-10">{avgRel}%</p>
          <p className="text-xs text-muted mt-2 relative z-10">متوسط دقة النصوص اللي رجعت من الـ Vector DB.</p>
        </Card>

        <Card className="p-6 bg-gradient-to-br from-card to-background border-warning/30 shadow-sm relative overflow-hidden">
          <div className="absolute top-0 right-0 p-4 opacity-10"><Database className="size-20" /></div>
          <div className="flex items-center gap-3 mb-2 relative z-10">
            <span className="grid size-10 place-items-center rounded-xl bg-warning/15 text-warning"><Database className="size-5" /></span>
            <h3 className="text-sm font-semibold">دقة الـ Text-to-SQL</h3>
          </div>
          <p className="text-4xl font-bold relative z-10">{avgSql}%</p>
          <p className="text-xs text-muted mt-2 relative z-10">متوسط جودة استعلامات الـ SQL المكتوبة.</p>
        </Card>
      </div>

      {/* سجل التقييمات */}
      <Card>
        <div className="border-b border-border px-5 py-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold flex items-center gap-2"><Activity className="size-4 text-primary" /> سجل التقييمات الأخيرة</h3>
          <Badge tone="primary">{history.length} سؤال</Badge>
        </div>
        
        {history.length === 0 ? (
          <div className="p-12 text-center text-muted flex flex-col items-center">
            <BarChart3 className="size-12 mb-4 opacity-20" />
            <p className="text-lg font-medium">لا يوجد تقييمات بعد</p>
            <p className="text-sm mt-1">اذهب إلى صفحة المحادثة، واضغط على "تقييم دقة الإجابة" تحت أي رد لتظهر النتائج هنا.</p>
          </div>
        ) : (
          <ul className="divide-y divide-border/60">
            {history.map((r, i) => (
              <li key={i} className="p-5 flex flex-col gap-3 hover:bg-elevated/20 transition-colors">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-sm font-semibold" dir="auto">{r.question}</p>
                  
                  {/* شارات التقييم */}
                  <div className="flex items-center gap-2">
                    {r.type === "sql" ? (
                      <Badge tone={r.score! >= 70 ? "success" : "danger"} className="text-xs px-2.5 py-1">
                        {r.score! >= 70 ? <CheckCircle2 className="size-3 me-1"/> : <AlertCircle className="size-3 me-1"/>}
                        SQL: {r.score}%
                      </Badge>
                    ) : (
                      <>
                        <Badge tone={r.faithfulness! >= 70 ? "success" : "danger"} className="text-xs px-2.5 py-1">
                          أمانة: {r.faithfulness}%
                        </Badge>
                        <Badge tone={r.relevance! >= 70 ? "success" : "danger"} className="text-xs px-2.5 py-1">
                          ملاءمة: {r.relevance}%
                        </Badge>
                      </>
                    )}
                  </div>
                </div>
                
                <div className="text-xs text-muted flex items-center gap-1.5 bg-background/40 p-2 rounded-lg w-fit">
                  <span className="font-semibold text-foreground">تقييم الموديل:</span> {r.reason}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </Page>
  );
}