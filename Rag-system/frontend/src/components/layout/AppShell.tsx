import { useCallback, useRef, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { BookOpen, ChevronDown, Database, FlaskConical, FolderOpen, Languages, LayoutDashboard, LogOut, Menu, MessageSquare, Settings, Users, Video, X } from "lucide-react";
import { Badge, Logo } from "@/components/ui";
import { useAuth } from "@/hooks/auth";
import { useClickAway } from "@/hooks/useClickAway";
import { useProject } from "@/hooks/project";
import { useI18n } from "@/i18n";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", key: "nav.dashboard", icon: LayoutDashboard, end: true },
  { to: "/projects", key: "nav.projects", icon: FolderOpen },
  { to: "/chat", key: "nav.chat", icon: MessageSquare },
  { to: "/knowledge", key: "nav.knowledge", icon: BookOpen },
  { to: "/video", key: "nav.video", icon: Video },
  { to: "/data", key: "nav.data", icon: Database },
  { to: "/evaluation", key: "nav.evaluation", icon: FlaskConical },
  { to: "/settings", key: "nav.settings", icon: Settings },
];

function NavItem({ to, label, icon: Icon, end, onClick }: { to: string; label: string; icon: typeof Users; end?: boolean; onClick: () => void }) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onClick}
      className={({ isActive }) =>
        cn(
          "flex h-10 items-center gap-3 rounded-xl px-3 text-[14px] font-medium transition-colors",
          isActive ? "bg-primary-soft text-primary" : "text-foreground/80 hover:bg-elevated/60 hover:text-foreground",
        )
      }
    >
      <Icon className="size-[18px] shrink-0" />
      {label}
    </NavLink>
  );
}

function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const { user } = useAuth();

  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-black/60 lg:hidden" onClick={onClose} />}
      <aside
        className={cn(
          "fixed inset-y-0 start-0 z-40 flex w-64 flex-col border-e border-border bg-sidebar transition-transform lg:static",
          // slide it away only on small screens (and to the right side in RTL)
          open ? "translate-x-0" : "max-lg:-translate-x-full max-lg:rtl:translate-x-full",
        )}
      >
        <div className="flex h-16 items-center justify-between px-5">
          <Logo />
          <button onClick={onClose} className="rounded-lg p-1.5 text-muted hover:text-foreground lg:hidden" aria-label="close menu">
            <X className="size-5" />
          </button>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto px-3 pb-4 pt-3">
          <p className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted/80">{t("nav.workspace")}</p>
          {NAV.map((item) => (
            <NavItem key={item.to} to={item.to} label={t(item.key)} icon={item.icon} end={item.end} onClick={onClose} />
          ))}

          {user?.role === "admin" && (
            <>
              <p className="px-3 pb-2 pt-6 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted/80">{t("nav.admin")}</p>
              <NavItem to="/admin/users" label={t("nav.users")} icon={Users} onClick={onClose} />
            </>
          )}
        </nav>
      </aside>
    </>
  );
}

function ProjectChip() {
  const { t } = useI18n();
  const { projectId, setProjectId } = useProject();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(String(projectId));
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useClickAway(ref, close, open);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => {
          setDraft(String(projectId));
          setOpen((v) => !v);
        }}
        className="flex h-9 items-center gap-2 rounded-xl border border-border bg-card px-3 text-[13px] hover:bg-elevated/60"
      >
        <FolderOpen className="size-4 text-primary" />
        <span className="text-muted">{t("common.project")}</span>
        <span dir="ltr" className="font-semibold">#{projectId}</span>
        <ChevronDown className="size-3.5 text-muted" />
      </button>

      {open && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setProjectId(Number(draft));
            setOpen(false);
          }}
          className="absolute start-0 top-11 z-20 w-56 animate-fade-in rounded-xl border border-border bg-card p-3 shadow-2xl"
        >
          <label className="mb-1.5 block text-xs text-muted">{t("common.project")} #</label>
          <div className="flex gap-2">
            <input
              type="number"
              min={1}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              dir="ltr"
              className="h-9 w-full rounded-lg border border-border bg-background px-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
            <button type="submit" className="h-9 rounded-lg bg-primary px-3 text-sm font-medium text-white">
              OK
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

function UserMenu() {
  const { t } = useI18n();
  const { user, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useClickAway(ref, close, open);

  if (!user) return null;

  const identifier = user.email ?? user.phone ?? "";
  const label = user.name || identifier;
  const initials = label.trim().slice(0, 2).toUpperCase();

  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen((v) => !v)} className="flex items-center gap-2.5 rounded-xl p-1 pe-2.5 hover:bg-elevated/60">
        <span className="grid size-9 place-items-center rounded-full bg-primary/20 text-[13px] font-semibold text-primary">{initials}</span>
        <span className="hidden text-start leading-tight sm:block">
          <span className="block max-w-[150px] truncate text-[13px] font-semibold">{label}</span>
          <span className="block text-[11px] text-muted">{user.role === "admin" ? t("common.admin") : t("common.user")}</span>
        </span>
      </button>

      {open && (
        <div className="absolute end-0 top-12 z-20 w-64 animate-fade-in rounded-xl border border-border bg-card p-2 shadow-2xl">
          <div className="border-b border-border px-3 pb-3 pt-2">
            <p className="truncate text-sm font-semibold">{label}</p>
            <p dir="ltr" className="truncate text-start text-xs text-muted">{identifier}</p>
            <Badge tone={user.role === "admin" ? "primary" : "neutral"} className="mt-2">
              {user.role === "admin" ? t("common.admin") : t("common.user")}
            </Badge>
          </div>
          <button onClick={() => signOut()} className="mt-1 flex h-10 w-full items-center gap-2.5 rounded-lg px-3 text-sm text-danger hover:bg-danger/10">
            <LogOut className="size-4" />
            {t("common.signOut")}
          </button>
        </div>
      )}
    </div>
  );
}

export function AppShell() {
  const { t, toggle } = useI18n();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center justify-between gap-3 border-b border-border px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <button onClick={() => setMenuOpen(true)} className="rounded-lg p-2 text-muted hover:bg-elevated/60 hover:text-foreground lg:hidden" aria-label="open menu">
              <Menu className="size-5" />
            </button>
            <ProjectChip />
          </div>

          <div className="flex items-center gap-1.5">
            <button onClick={toggle} className="inline-flex h-9 items-center gap-2 rounded-lg px-3 text-[13px] text-muted hover:bg-elevated/60 hover:text-foreground">
              <Languages className="size-4" />
              {t("common.language")}
            </button>
            <UserMenu />
          </div>
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
