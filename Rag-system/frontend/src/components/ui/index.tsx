import { useEffect, useRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from "react";
import { AlertCircle, CheckCircle2, Loader2, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

/* ---------------------------------------------------------------- Button */

type Variant = "primary" | "secondary" | "ghost" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "sm" | "md" | "lg";
  loading?: boolean;
}

const variants: Record<Variant, string> = {
  primary: "bg-primary text-white hover:bg-primary/90 shadow-[0_8px_24px_-12px_rgb(var(--primary)/.8)]",
  secondary: "bg-elevated text-foreground border border-border hover:bg-elevated/70",
  ghost: "text-muted hover:text-foreground hover:bg-elevated/60",
  danger: "bg-danger/15 text-danger border border-danger/30 hover:bg-danger/25",
};

const sizes = { sm: "h-8 px-3 text-[13px]", md: "h-10 px-4 text-sm", lg: "h-12 px-5 text-[15px]" };

export function Button({ variant = "primary", size = "md", loading, className, children, disabled, ...props }: ButtonProps) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 disabled:cursor-not-allowed disabled:opacity-55",
        variants[variant],
        sizes[size],
        className,
      )}
    >
      {loading && <Loader2 className="size-4 animate-spin" />}
      {children}
    </button>
  );
}

/* ----------------------------------------------------------------- Input */

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  icon?: ReactNode;
  trailing?: ReactNode;
  ltr?: boolean;
}

export function Input({ label, error, hint, icon, trailing, ltr, className, id, ...props }: InputProps) {
  const inputId = id ?? props.name;

  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={inputId} className="block text-[13px] font-medium text-foreground/90">
          {label}
        </label>
      )}
      <div className="relative">
        {icon && <span className="pointer-events-none absolute inset-y-0 start-3 flex items-center text-muted">{icon}</span>}
        <input
          id={inputId}
          dir={ltr ? "ltr" : undefined}
          {...props}
          className={cn(
            "h-11 w-full rounded-xl border bg-background/60 px-3.5 text-sm text-foreground placeholder:text-muted/60",
            "transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50",
            error ? "border-danger/60" : "border-border focus:border-primary/60",
            icon && "ps-10",
            trailing && "pe-16",
            ltr && "text-start",
            className,
          )}
        />
        {trailing && <span className="absolute inset-y-0 end-2 flex items-center">{trailing}</span>}
      </div>
      {error ? <p className="text-xs text-danger">{error}</p> : hint ? <p className="text-xs text-muted">{hint}</p> : null}
    </div>
  );
}

/* ------------------------------------------------------- Card / Badge / … */

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("rounded-2xl border border-border bg-card", className)}>{children}</div>;
}

export function Badge({ tone = "neutral", children, className }: { tone?: "neutral" | "primary" | "success" | "warning" | "danger"; children: ReactNode; className?: string }) {
  const tones = {
    neutral: "bg-elevated text-muted border-border",
    primary: "bg-primary/15 text-primary border-primary/30",
    success: "bg-success/15 text-success border-success/30",
    warning: "bg-warning/15 text-warning border-warning/30",
    danger: "bg-danger/15 text-danger border-danger/30",
  };
  return <span className={cn("inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium", tones[tone], className)}>{children}</span>;
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("size-5 animate-spin text-primary", className)} />;
}

export function Alert({ tone = "danger", children }: { tone?: "danger" | "success"; children: ReactNode }) {
  const Icon = tone === "danger" ? AlertCircle : CheckCircle2;
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={cn(
        "flex items-start gap-2.5 rounded-xl border px-3.5 py-3 text-sm animate-fade-in",
        tone === "danger" ? "border-danger/30 bg-danger/10 text-danger" : "border-success/30 bg-success/10 text-success",
      )}
    >
      <Icon className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

export function Segmented<T extends string>({ value, onChange, options }: { value: T; onChange: (value: T) => void; options: { value: T; label: string }[] }) {
  return (
    <div className="grid rounded-xl border border-border bg-background/60 p-1" style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={cn(
            "h-9 rounded-lg text-[13px] font-medium transition-colors",
            value === option.value ? "bg-elevated text-foreground shadow-sm" : "text-muted hover:text-foreground",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function Logo({ size = "md" }: { size?: "md" | "lg" }) {
  return (
    <div className="flex items-center gap-3">
      <div className={cn("grid place-items-center rounded-xl bg-primary text-white shadow-[0_10px_30px_-10px_rgb(var(--primary))]", size === "lg" ? "size-11" : "size-9")}>
        <Sparkles className={size === "lg" ? "size-5" : "size-[18px]"} />
      </div>
      <span className={cn("font-semibold tracking-tight", size === "lg" ? "text-xl" : "text-[17px]")}>RAG System</span>
    </div>
  );
}

/* -------------------------------------------------------------- OTP input */

export function OtpInput({ value, onChange, length = 6, autoFocus, disabled }: { value: string; onChange: (value: string) => void; length?: number; autoFocus?: boolean; disabled?: boolean }) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    if (autoFocus) refs.current[0]?.focus();
  }, [autoFocus]);

  const digits = Array.from({ length }, (_, i) => value[i] ?? "");

  function set(index: number, digit: string) {
    const next = digits.slice();
    next[index] = digit;
    onChange(next.join(""));
  }

  return (
    <div dir="ltr" className="flex justify-center gap-2.5">
      {digits.map((digit, index) => (
        <input
          key={index}
          ref={(el) => {
            refs.current[index] = el;
          }}
          value={digit}
          disabled={disabled}
          inputMode="numeric"
          autoComplete={index === 0 ? "one-time-code" : "off"}
          aria-label={`digit ${index + 1}`}
          maxLength={1}
          onChange={(e) => {
            const char = e.target.value.replace(/\D/g, "").slice(-1);
            set(index, char);
            if (char && index < length - 1) refs.current[index + 1]?.focus();
          }}
          onKeyDown={(e) => {
            if (e.key === "Backspace" && !digit && index > 0) refs.current[index - 1]?.focus();
            if (e.key === "ArrowLeft" && index > 0) refs.current[index - 1]?.focus();
            if (e.key === "ArrowRight" && index < length - 1) refs.current[index + 1]?.focus();
          }}
          onPaste={(e) => {
            const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, length);
            if (!pasted) return;
            e.preventDefault();
            onChange(pasted);
            refs.current[Math.min(pasted.length, length - 1)]?.focus();
          }}
          className={cn(
            "size-12 rounded-xl border bg-background/60 text-center text-xl font-semibold tabular-nums transition-colors sm:size-[52px]",
            "focus:outline-none focus:ring-2 focus:ring-primary/50",
            digit ? "border-primary/60" : "border-border",
          )}
        />
      ))}
    </div>
  );
}
