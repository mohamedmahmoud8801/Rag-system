import { useState, type ReactNode } from "react";
import { Eye, EyeOff, Lock } from "lucide-react";
import { Input } from "@/components/ui";
import { useI18n } from "@/i18n";

export function AuthHeading({ title, subtitle }: { title: string; subtitle?: ReactNode }) {
  return (
    <div className="mb-7">
      <h1 className="text-[28px] font-semibold tracking-tight">{title}</h1>
      {subtitle && <p className="mt-2 text-[15px] leading-relaxed text-muted">{subtitle}</p>}
    </div>
  );
}

export function PasswordField({ label, value, onChange, hint, autoComplete, error }: { label: string; value: string; onChange: (value: string) => void; hint?: string; autoComplete?: string; error?: string }) {
  const { t } = useI18n();
  const [visible, setVisible] = useState(false);

  return (
    <Input
      label={label}
      name="password"
      type={visible ? "text" : "password"}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      autoComplete={autoComplete}
      icon={<Lock className="size-4" />}
      hint={hint}
      error={error}
      ltr
      trailing={
        <button type="button" onClick={() => setVisible((v) => !v)} className="rounded-md px-2 py-1 text-xs text-muted hover:text-foreground" aria-label={visible ? t("auth.hide") : t("auth.show")}>
          {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      }
    />
  );
}

/** the identifier as the user should read it: +201012345678 stays left-to-right */
export function Ident({ value }: { value: string }) {
  return (
    <span dir="ltr" className="font-medium text-foreground">
      {value}
    </span>
  );
}
