import type { ReactNode } from "react";
import { FileSearch, Languages, Sparkles, Table2 } from "lucide-react";
import { Logo } from "@/components/ui";
import { useI18n } from "@/i18n";

export function AuthLayout({ children }: { children: ReactNode }) {
  const { t, toggle } = useI18n();

  const features = [
    { icon: FileSearch, text: t("brand.f1") },
    { icon: Table2, text: t("brand.f2") },
    { icon: Sparkles, text: t("brand.f3") },
  ];

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <aside className="relative hidden overflow-hidden border-e border-border bg-sidebar p-12 lg:flex lg:flex-col lg:justify-between">
        <div className="pointer-events-none absolute -top-40 start-[-10%] size-[520px] rounded-full bg-primary/20 blur-[120px]" />
        <div className="pointer-events-none absolute -bottom-52 end-[-15%] size-[480px] rounded-full bg-sky-400/10 blur-[120px]" />
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{ backgroundImage: "radial-gradient(rgb(var(--foreground)) 1px, transparent 1px)", backgroundSize: "26px 26px" }}
        />
        <div className="relative">
          <Logo size="lg" />
        </div>
        <div className="relative max-w-md">
          <h2 className="text-4xl font-semibold leading-[1.25] tracking-tight">{t("app.tagline")}</h2>
          <ul className="mt-10 space-y-4">
            {features.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-3.5 text-[15px] text-foreground/85">
                <span className="grid size-9 shrink-0 place-items-center rounded-lg border border-border bg-card/70 text-primary">
                  <Icon className="size-[18px]" />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-muted">© RAG System</p>
      </aside>

      <main className="relative flex items-center justify-center px-5 py-10">
        <button
          type="button"
          onClick={toggle}
          className="absolute end-5 top-5 inline-flex items-center gap-2 rounded-lg px-3 py-2 text-[13px] text-muted transition-colors hover:bg-elevated/60 hover:text-foreground"
        >
          <Languages className="size-4" />
          {t("common.language")}
        </button>
        <div className="w-full max-w-[420px] animate-fade-in">
          <div className="mb-8 lg:hidden">
            <Logo />
          </div>
          {children}
        </div>
      </main>
    </div>
  );
}
