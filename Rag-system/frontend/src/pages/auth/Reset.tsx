import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { Alert, Button, OtpInput } from "@/components/ui";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { useCountdown } from "@/hooks/useCountdown";
import { useI18n } from "@/i18n";
import { api, ApiError } from "@/lib/api";
import { AuthHeading, Ident, PasswordField } from "./shared";

export default function Reset() {
  const { t, errorText } = useI18n();
  const navigate = useNavigate();
  const identifier = (useLocation().state as { identifier?: string } | null)?.identifier;

  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [resent, setResent] = useState(false);
  const countdown = useCountdown(60);

  if (!identifier) return <Navigate to="/forgot" replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);

    try {
      await api("/api/v1/auth/password/reset", { body: { identifier, code, new_password: password }, auth: false });
      navigate("/login", { replace: true, state: { notice: "resetDone" } });
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, "unknown", ""));
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    setError(null);
    setResent(false);

    try {
      await api("/api/v1/auth/password/forgot", { body: { identifier }, auth: false });
      setResent(true);
      countdown.start(60);
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, "unknown", ""));
      if (e instanceof ApiError && e.retryAfter) countdown.start(e.retryAfter);
    }
  }

  return (
    <AuthLayout>
      <AuthHeading
        title={t("auth.reset.title")}
        subtitle={
          <>
            {t("auth.reset.sub")} <Ident value={identifier} />
          </>
        }
      />

      <form onSubmit={submit} className="space-y-6">
        {error && <Alert>{errorText(error)}</Alert>}
        {resent && !error && <Alert tone="success">{t("auth.codeResent")}</Alert>}

        <OtpInput value={code} onChange={setCode} autoFocus />
        <PasswordField label={t("auth.newPassword")} value={password} onChange={setPassword} autoComplete="new-password" hint={t("auth.passwordHint")} />

        <Button type="submit" size="lg" className="w-full" loading={busy} disabled={code.length !== 6 || password.length < 8}>
          {t("auth.reset")}
        </Button>

        <div className="space-y-3 text-center">
          <button type="button" disabled={countdown.left > 0} onClick={resend} className="text-[13px] text-primary disabled:text-muted">
            {countdown.left > 0 ? t("auth.resendIn", { s: countdown.left }) : t("auth.resend")}
          </button>
          <p>
            <Link to="/login" className="text-[13px] text-muted hover:text-foreground">
              {t("auth.backToSignIn")}
            </Link>
          </p>
        </div>
      </form>
    </AuthLayout>
  );
}
