import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AtSign, User } from "lucide-react";
import { Alert, Button, Input } from "@/components/ui";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { useI18n } from "@/i18n";
import { api, ApiError } from "@/lib/api";
import { AuthHeading, PasswordField } from "./shared";

export default function Register() {
  const { t, errorText } = useI18n();
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);

    try {
      const result = await api<{ identifier: string }>("/api/v1/auth/register", { body: { identifier, password, name: name || null }, auth: false });
      navigate("/verify", { state: { identifier: result.identifier } });
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, "unknown", ""));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <AuthHeading title={t("auth.register.title")} subtitle={t("auth.register.sub")} />

      <form onSubmit={submit} className="space-y-4">
        {error && (
          <Alert>
            <p>{errorText(error)}</p>
            {error.code === "already_registered" && (
              <Link to="/login" className="mt-1 inline-block font-medium underline underline-offset-2">
                {t("auth.signIn")}
              </Link>
            )}
          </Alert>
        )}

        <Input label={t("auth.name")} name="name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" icon={<User className="size-4" />} />
        <Input label={t("auth.email_or_phone")} name="identifier" value={identifier} onChange={(e) => setIdentifier(e.target.value)} placeholder={t("auth.email_or_phone.ph")} autoComplete="username" icon={<AtSign className="size-4" />} ltr required />
        <PasswordField label={t("auth.password")} value={password} onChange={setPassword} autoComplete="new-password" hint={t("auth.passwordHint")} />

        <Button type="submit" size="lg" className="w-full" loading={busy} disabled={!identifier || password.length < 8}>
          {t("auth.createAccount")}
        </Button>

        <p className="pt-2 text-center text-sm text-muted">
          {t("auth.haveAccount")}{" "}
          <Link to="/login" className="font-medium text-primary hover:underline">
            {t("auth.signIn")}
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}
