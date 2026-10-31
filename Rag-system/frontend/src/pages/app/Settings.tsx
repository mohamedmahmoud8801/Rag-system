import { useState } from "react";
import { LogOut, RotateCcw, User as UserIcon } from "lucide-react";
import { Page, PageHeader } from "@/components/layout/PageHeader";
import { Badge, Button, Card } from "@/components/ui";
import { useAuth } from "@/hooks/auth";
import { useProject } from "@/hooks/project";
import { useI18n } from "@/i18n";

export default function Settings() {
  const { t, lang, toggle } = useI18n();
  const { user, signOut } = useAuth();
  const { projectId } = useProject();
  const [confirm, setConfirm] = useState(false);

  const identifier = user?.email ?? user?.phone ?? "";

  function clearAllLocal() {
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const k = localStorage.key(i);
      if (!k) continue;
      if (
        k.startsWith("rag.files.") ||
        k.startsWith("rag.excel.") ||
        (k.startsWith("rag.chat.") && k !== "rag.chat.mode")
      ) {
        localStorage.removeItem(k);
      }
    }
    setConfirm(false);
    window.location.reload();
  }

  return (
    <Page>
      <PageHeader title={t("settings.title")} subtitle={t("settings.subtitle")} />

      <Card className="mb-4 p-5">
        <div className="mb-3 flex items-center gap-2">
          <UserIcon className="size-4 text-primary" />
          <h3 className="text-sm font-semibold">{t("settings.account")}</h3>
        </div>
        {user ? (
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs text-muted">{t("settings.name")}</dt>
              <dd className="font-medium">{user.name || "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted">{t("settings.identifier")}</dt>
              <dd className="font-medium" dir="ltr">{identifier || "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted">{t("settings.role")}</dt>
              <dd><Badge tone={user.role === "admin" ? "primary" : "neutral"}>{user.role === "admin" ? t("common.admin") : t("common.user")}</Badge></dd>
            </div>
            <div>
              <dt className="text-xs text-muted">{t("settings.status")}</dt>
              <dd><Badge tone={user.is_active ? "success" : "danger"}>{user.is_active ? t("common.active") : t("common.disabled")}</Badge></dd>
            </div>
          </dl>
        ) : (
          <p className="text-sm text-muted">{t("common.loading")}</p>
        )}
        <p className="mt-3 text-xs text-muted">{t("settings.account.hint")}</p>
      </Card>

      <Card className="mb-4 p-5">
        <h3 className="mb-3 text-sm font-semibold">{t("settings.prefs")}</h3>
        <div className="space-y-3">
          <div className="flex items-center justify-between rounded-lg border border-border bg-background/40 p-3">
            <div>
              <p className="text-sm font-medium">{t("settings.language")}</p>
              <p className="text-xs text-muted">{lang === "ar" ? "العربية" : "English"}</p>
            </div>
            <Button variant="secondary" size="sm" onClick={toggle}>{t("common.language")}</Button>
          </div>
          <div className="flex items-center justify-between rounded-lg border border-border bg-background/40 p-3">
            <div>
              <p className="text-sm font-medium">{t("settings.currentProject")}</p>
              <p className="text-xs text-muted" dir="ltr">#{projectId}</p>
            </div>
            <Badge tone="primary">#{projectId}</Badge>
          </div>
        </div>
      </Card>

      <Card className="mb-4 p-5">
        <div className="mb-3 flex items-center gap-2">
          <RotateCcw className="size-4 text-warning" />
          <h3 className="text-sm font-semibold">{t("settings.danger")}</h3>
        </div>
        <p className="mb-3 text-sm text-muted">{t("settings.danger.hint")}</p>
        <Button variant="danger" size="sm" onClick={() => setConfirm(true)}><RotateCcw className="size-4" /> {t("settings.reset")}</Button>
      </Card>

      <Card className="p-5">
        <h3 className="mb-3 text-sm font-semibold">{t("settings.session")}</h3>
        <Button variant="secondary" onClick={() => signOut()}><LogOut className="size-4" /> {t("common.signOut")}</Button>
      </Card>

      {confirm && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" onClick={() => setConfirm(false)}>
          <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-base font-semibold">{t("settings.reset.title")}</h3>
            <p className="mt-2 text-sm text-muted">{t("settings.reset.hint")}</p>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setConfirm(false)}>{t("common.cancel")}</Button>
              <Button variant="danger" onClick={clearAllLocal}><RotateCcw className="size-4" /> {t("settings.reset.confirm")}</Button>
            </div>
          </div>
        </div>
      )}
    </Page>
  );
}