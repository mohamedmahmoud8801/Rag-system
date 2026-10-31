import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError } from "@/lib/api";
import ar from "./ar";
import en from "./en";

export type Lang = "ar" | "en";

const dictionaries: Record<Lang, Record<string, string>> = { ar, en };
const STORAGE_KEY = "rag.lang";

interface I18n {
  lang: Lang;
  dir: "rtl" | "ltr";
  locale: string;
  t: (key: string, vars?: Record<string, string | number>) => string;
  toggle: () => void;
  /** a user-facing sentence for any error */
  errorText: (error: unknown) => string;
}

const Ctx = createContext<I18n | null>(null);

function initialLang(): Lang {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === "ar" || saved === "en") return saved;
  return navigator.language?.toLowerCase().startsWith("ar") ? "ar" : "en";
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(initialLang);
  const dir = lang === "ar" ? "rtl" : "ltr";

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = dir;
    localStorage.setItem(STORAGE_KEY, lang);
  }, [lang, dir]);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => {
      let text = dictionaries[lang][key] ?? dictionaries.en[key] ?? key;
      if (vars) for (const [k, v] of Object.entries(vars)) text = text.replace(`{${k}}`, String(v));
      return text;
    },
    [lang],
  );

  const value = useMemo<I18n>(
    () => ({
      lang,
      dir,
      locale: lang === "ar" ? "ar-EG" : "en-US",
      t,
      toggle: () => setLang((l) => (l === "ar" ? "en" : "ar")),
      errorText: (error: unknown) => {
        if (error instanceof ApiError) {
          // If it's a network error or timeout
          if (error.status === 0 || error.code === "network_error") {
            return t("err.network_error");
          }
          // If it's a server crash (500+)
          if (error.status >= 500) {
            return t("err.server_error");
          }
          
          // Known API errors
          const key = `err.${error.code}`;
          if (dictionaries[lang][key]) {
            return t(key);
          }
          
          // Fallback for unknown API errors
          return t("err.unknown");
        }
        
        // Fallback for completely unexpected errors
        return t("err.unknown");
      },
    }),
    [lang, dir, t],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n(): I18n {
  const value = useContext(Ctx);
  if (!value) throw new Error("useI18n must be used inside LanguageProvider");
  return value;
}