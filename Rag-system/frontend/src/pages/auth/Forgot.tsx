import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AtSign } from "lucide-react";
import { Alert, Button, Input } from "@/components/ui";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { useI18n } from "@/i18n";
import { api, ApiError } from "@/lib/api";
import { AuthHeading } from "./shared";

export default function Forgot() {
  const { t, errorText } = useI18n();
  const navigate = useNavigate();

  const [identifier, setIdentifier] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);

    try {
      await api("/api/v1/auth/password/forgot", { body: { identifier }, auth: false });
      navigate("/reset", { state: { identifier } });
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, "unknown", ""));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <AuthHeading title={t("auth.forgot.title")} subtitle={t("auth.forgot.sub")} />

      <form onSubmit={submit} className="space-y-4">
        {error && <Alert>{errorText(error)}</Alert>}

        <Input label={t("auth.email_or_phone")} name="identifier" value={identifier} onChange={(e) => setIdentifier(e.target.value)} placeholder={t("auth.email_or_phone.ph")} autoComplete="username" icon={<AtSign className="size-4" />} ltr required />

        <Button type="submit" size="lg" className="w-full" loading={busy} disabled={!identifier}>
          {t("auth.sendCode")}
        </Button>

        <p className="pt-2 text-center">
          <Link to="/login" className="text-[13px] text-muted hover:text-foreground">
            {t("auth.backToSignIn")}
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}
