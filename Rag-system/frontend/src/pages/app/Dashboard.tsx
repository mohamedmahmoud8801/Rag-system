import { Link } from "react-router-dom";
import { ArrowUpRight, BookOpen, Database, MessageSquare, Video } from "lucide-react";
import { Page } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui";
import { useAuth } from "@/hooks/auth";
import { useI18n } from "@/i18n";

export default function Dashboard() {
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const name = user?.name || user?.email || user?.phone || "";

  const tiles = [
    { to: "/chat", icon: MessageSquare, title: t("nav.chat"), text: t("chat.subtitle") },
    { to: "/data", icon: Database, title: t("nav.data"), text: lang === "ar" ? "ارفع Excel أو اربط قاعدة بيانات واسألها بالعربي." : "Upload Excel or connect a database and ask in plain language." },
    { to: "/knowledge", icon: BookOpen, title: t("nav.knowledge"), text: lang === "ar" ? "ملخصات وبطاقات واختبارات من مستنداتك." : "Summaries, flashcards and quizzes from your documents." },
    { to: "/video", icon: Video, title: t("nav.video"), text: lang === "ar" ? "حوّل فيديو يوتيوب إلى مادة قابلة للسؤال." : "Turn a YouTube video into something you can question." },
  ];

  return (
    <Page>
      <h1 className="text-[28px] font-semibold tracking-tight">
        {lang === "ar" ? "أهلًا" : "Welcome back"}, {name}
      </h1>
      <p className="mt-1.5 text-[15px] text-muted">{lang === "ar" ? "ابدأ من هنا." : "Start from here."}</p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        {tiles.map(({ to, icon: Icon, title, text }) => (
          <Link key={to} to={to} className="group">
            <Card className="flex h-full items-start gap-4 p-6 transition-colors group-hover:border-primary/50 group-hover:bg-card/80">
              <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary/15 text-primary">
                <Icon className="size-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[16px] font-semibold">{title}</p>
                <p className="mt-1 text-[13.5px] leading-relaxed text-muted">{text}</p>
              </div>
              <ArrowUpRight className="size-5 shrink-0 text-muted transition-colors group-hover:text-primary rtl:-scale-x-100" />
            </Card>
          </Link>
        ))}
      </div>
    </Page>
  );
}
