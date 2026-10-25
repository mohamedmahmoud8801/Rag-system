import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { Alert, Button, OtpInput } from "@/components/ui";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { useAuth } from "@/hooks/auth";
import { useCountdown } from "@/hooks/useCountdown";
import { useI18n } from "@/i18n";
import { api, ApiError, type Tokens } from "@/lib/api";
import { AuthHeading, Ident } from "./shared";

export default function Verify() {
  const { t, errorText } = useI18n();
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const identifier = (useLocation().state as { identifier?: string } | null)?.identifier;

  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [resent, setResent] = useState(false);
  const countdown = useCountdown(60);

  if (!identifier) return <Navigate to="/register" replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);

    try {
      signIn(await api<Tokens>("/api/v1/auth/verify", { body: { identifier, code }, auth: false }));
      navigate("/", { replace: true });
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, "unknown", ""));
      setCode("");
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    setError(null);
    setResent(false);

    try {
      await api("/api/v1/auth/resend", { body: { identifier }, auth: false });
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
        title={t("auth.verify.title")}
        subtitle={
          <>
            {t("auth.verify.sub")} <Ident value={identifier} />
          </>
        }
      />

      <form onSubmit={submit} className="space-y-6">
        {error && <Alert>{errorText(error)}</Alert>}
        {resent && !error && <Alert tone="success">{t("auth.codeResent")}</Alert>}

        <OtpInput value={code} onChange={setCode} autoFocus />

        <Button type="submit" size="lg" className="w-full" loading={busy} disabled={code.length !== 6}>
          {t("auth.verify")}
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
