import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Page, PageHeader } from "@/components/layout/PageHeader";
import { Alert, Badge, Button, Card, Spinner } from "@/components/ui";
import { useAuth } from "@/hooks/auth";
import { useI18n } from "@/i18n";
import { api, type User } from "@/lib/api";
import { formatDate } from "@/lib/utils";

export default function AdminUsers() {
  const { t, errorText, locale } = useI18n();
  const { user: me } = useAuth();
  const client = useQueryClient();

  const users = useQuery({ queryKey: ["users"], queryFn: () => api<{ users: User[] }>("/api/v1/auth/users") });

  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: { role?: string; is_active?: boolean } }) => api(`/api/v1/auth/users/${id}`, { method: "PATCH", body }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["users"] }),
  });

  return (
    <Page>
      <PageHeader title={t("users.title")} subtitle={t("users.subtitle")} />

      {users.isLoading && (
        <div className="grid place-items-center py-20">
          <Spinner />
        </div>
      )}
      {users.error && <Alert>{errorText(users.error)}</Alert>}
      {update.error && <Alert>{errorText(update.error)}</Alert>}

      {users.data && (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-border text-start text-[12px] uppercase tracking-wider text-muted">
                {["users.col.user", "users.col.role", "users.col.status", "users.col.joined"].map((key) => (
                  <th key={key} className="px-5 py-3.5 text-start font-medium">{t(key)}</th>
                ))}
                <th className="px-5 py-3.5" />
              </tr>
            </thead>
            <tbody>
              {users.data.users.map((u) => {
                const isMe = u.id === me?.id;
                const identifier = u.email ?? u.phone ?? "";

                return (
                  <tr key={u.id} className="border-b border-border/60 last:border-0">
                    <td className="px-5 py-4">
                      <p className="font-medium">{u.name || identifier}</p>
                      <p dir="ltr" className="text-start text-xs text-muted">{identifier}</p>
                    </td>
                    <td className="px-5 py-4">
                      <Badge tone={u.role === "admin" ? "primary" : "neutral"}>{u.role === "admin" ? t("common.admin") : t("common.user")}</Badge>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex flex-wrap gap-1.5">
                        <Badge tone={u.is_active ? "success" : "danger"}>{u.is_active ? t("common.active") : t("common.disabled")}</Badge>
                        <Badge tone={u.email_verified || u.phone_verified ? "neutral" : "warning"}>{u.email_verified || u.phone_verified ? t("common.verified") : t("common.unverified")}</Badge>
                      </div>
                    </td>
                    <td className="px-5 py-4 text-muted">{formatDate(u.created_at, locale)}</td>
                    <td className="px-5 py-4">
                      {isMe ? (
                        <Badge>{t("users.you")}</Badge>
                      ) : (
                        <div className="flex justify-end gap-2">
                          <Button variant="secondary" size="sm" disabled={update.isPending} onClick={() => update.mutate({ id: u.id, body: { role: u.role === "admin" ? "user" : "admin" } })}>
                            {u.role === "admin" ? t("users.makeUser") : t("users.makeAdmin")}
                          </Button>
                          <Button variant={u.is_active ? "danger" : "secondary"} size="sm" disabled={update.isPending} onClick={() => update.mutate({ id: u.id, body: { is_active: !u.is_active } })}>
                            {u.is_active ? t("users.disable") : t("users.enable")}
                          </Button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}
    </Page>
  );
}
