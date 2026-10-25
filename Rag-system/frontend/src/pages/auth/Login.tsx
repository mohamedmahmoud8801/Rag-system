import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { AtSign } from "lucide-react";
import { Alert, Button, Input, OtpInput, Segmented } from "@/components/ui";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { useAuth } from "@/hooks/auth";
import { useCountdown } from "@/hooks/useCountdown";
import { useI18n } from "@/i18n";
import { api, ApiError, type Tokens } from "@/lib/api";
import { AuthHeading, Ident, PasswordField } from "./shared";

export default function Login() {
  const { t, errorText } = useI18n();
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as { from?: string; notice?: string } | null;

  const [mode, setMode] = useState<"password" | "code">("password");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const countdown = useCountdown(60, false);

  const done = (tokens: Tokens) => {
    signIn(tokens);
    navigate(state?.from ?? "/", { replace: true });
  };

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, "unknown", ""));
    } finally {
      setBusy(false);
    }
  }

  const submitPassword = (e: FormEvent) => {
    e.preventDefault();
    return run(async () => done(await api<Tokens>("/api/v1/auth/login", { body: { identifier, password }, auth: false })));
  };

  const requestCode = (e?: FormEvent) => {
    e?.preventDefault();
    return run(async () => {
      await api("/api/v1/auth/login/code/request", { body: { identifier }, auth: false });
      setCodeSent(true);
      setCode("");
      countdown.start(60);
    });
  };

  const submitCode = (e: FormEvent) => {
    e.preventDefault();
    return run(async () => done(await api<Tokens>("/api/v1/auth/login/code/verify", { body: { identifier, code }, auth: false })));
  };

  const goVerify = () =>
    run(async () => {
      try {
        await api("/api/v1/auth/resend", { body: { identifier }, auth: false });
      } catch {
        /* a code may already have been sent a moment ago */
      }
      navigate("/verify", { state: { identifier } });
    });

  return (
    <AuthLayout>
      <AuthHeading title={t("auth.signIn.title")} subtitle={t("auth.signIn.sub")} />

      <div className="space-y-5">
        {state?.notice === "resetDone" && <Alert tone="success">{t("auth.resetDone")}</Alert>}

        <Segmented
          value={mode}
          onChange={(value) => {
            setMode(value);
            setError(null);
            setCodeSent(false);
          }}
          options={[
            { value: "password", label: t("auth.withPassword") },
            { value: "code", label: t("auth.withCode") },
          ]}
        />

        {error && (
          <Alert>
            <p>{errorText(error)}</p>
            {error.code === "not_verified" && (
              <button type="button" onClick={goVerify} className="mt-1.5 font-medium underline underline-offset-2">
                {t("auth.verify.title")}
              </button>
            )}
            {error.retryAfter && ["account_locked", "wait_before_resend"].includes(error.code) && (
              <p className="mt-1 text-xs opacity-80">{Math.ceil(error.retryAfter / 60) > 1 ? `${Math.ceil(error.retryAfter / 60)} min` : `${error.retryAfter}s`}</p>
            )}
          </Alert>
        )}

        {mode === "password" ? (
          <form onSubmit={submitPassword} className="space-y-4">
            <Input label={t("auth.email_or_phone")} name="identifier" value={identifier} onChange={(e) => setIdentifier(e.target.value)} placeholder={t("auth.email_or_phone.ph")} autoComplete="username" icon={<AtSign className="size-4" />} ltr required />
            <PasswordField label={t("auth.password")} value={password} onChange={setPassword} autoComplete="current-password" />
            <div className="flex justify-end">
              <Link to="/forgot" className="text-[13px] text-primary hover:underline">
                {t("auth.forgot")}
              </Link>
            </div>
            <Button type="submit" size="lg" className="w-full" loading={busy} disabled={!identifier || !password}>
              {t("auth.signIn")}
            </Button>
          </form>
        ) : !codeSent ? (
          <form onSubmit={requestCode} className="space-y-4">
            <Input label={t("auth.email_or_phone")} name="identifier" value={identifier} onChange={(e) => setIdentifier(e.target.value)} placeholder={t("auth.email_or_phone.ph")} autoComplete="username" icon={<AtSign className="size-4" />} ltr required />
            <Button type="submit" size="lg" className="w-full" loading={busy} disabled={!identifier}>
              {t("auth.sendCode")}
            </Button>
          </form>
        ) : (
          <form onSubmit={submitCode} className="space-y-6">
            <p className="text-center text-sm text-muted">
              {t("auth.codeSentTo")} <Ident value={identifier} />
            </p>
            <OtpInput value={code} onChange={setCode} autoFocus />
            <Button type="submit" size="lg" className="w-full" loading={busy} disabled={code.length !== 6}>
              {t("auth.verifyAndSignIn")}
            </Button>
            <button type="button" disabled={countdown.left > 0 || busy} onClick={() => requestCode()} className="block w-full text-center text-[13px] text-primary disabled:text-muted">
              {countdown.left > 0 ? t("auth.resendIn", { s: countdown.left }) : t("auth.resend")}
            </button>
          </form>
        )}

        <p className="pt-2 text-center text-sm text-muted">
          {t("auth.noAccount")}{" "}
          <Link to="/register" className="font-medium text-primary hover:underline">
            {t("auth.createAccount")}
          </Link>
        </p>
      </div>
    </AuthLayout>
  );
}
