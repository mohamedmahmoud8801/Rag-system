import type { LucideIcon } from "lucide-react";
import { Page, PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui";
import { useI18n } from "@/i18n";

export default function ComingSoon({ titleKey, icon: Icon }: { titleKey: string; icon: LucideIcon }) {
  const { t } = useI18n();

  return (
    <Page>
      <PageHeader title={t(titleKey)} />
      <Card className="grid place-items-center px-6 py-20 text-center">
        <span className="mb-4 grid size-14 place-items-center rounded-2xl bg-primary/15 text-primary">
          <Icon className="size-6" />
        </span>
        <p className="text-[15px] text-muted">{t("common.comingSoon")}</p>
      </Card>
    </Page>
  );
}
