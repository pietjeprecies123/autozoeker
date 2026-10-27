import clsx from "clsx";
import { Loader2, X } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { useEffect } from "react";

export function Button({
  variant = "primary",
  size = "md",
  className,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger"; size?: "sm" | "md" }) {
  return (
    <button
      className={clsx(
        "inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "px-2.5 py-1.5 text-xs" : "px-3.5 py-2 text-sm",
        variant === "primary" && "bg-brand-700 text-white hover:bg-brand-800",
        variant === "secondary" && "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
        variant === "ghost" && "text-slate-600 hover:bg-slate-100",
        variant === "danger" && "bg-rose-600 text-white hover:bg-rose-700",
        className,
      )}
      {...rest}
    />
  );
}

export function Card({ className, children, ...rest }: { className?: string; children: ReactNode } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={clsx("rounded-xl border border-slate-200 bg-white shadow-sm", className)} {...rest}>
      {children}
    </div>
  );
}

export function Section({ title, icon, actions, children, className }: { title: string; icon?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <Card className={clsx("p-5 print-break", className)}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
          {icon}
          {title}
        </h2>
        {actions}
      </div>
      {children}
    </Card>
  );
}

const TONES = {
  good: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  ok: "bg-slate-100 text-slate-700 ring-slate-500/20",
  bad: "bg-rose-50 text-rose-700 ring-rose-600/20",
  warn: "bg-amber-50 text-amber-800 ring-amber-600/20",
  info: "bg-sky-50 text-sky-700 ring-sky-600/20",
  brand: "bg-brand-50 text-brand-800 ring-brand-600/20",
  none: "bg-slate-50 text-slate-500 ring-slate-400/20",
  demo: "bg-violet-50 text-violet-700 ring-violet-600/20",
} as const;
export type Tone = keyof typeof TONES;

export function Badge({ tone = "ok", children, className, title }: { tone?: Tone; children: ReactNode; className?: string; title?: string }) {
  return (
    <span title={title} className={clsx("inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset", TONES[tone], className)}>
      {children}
    </span>
  );
}

export function severityTone(s: string | undefined): Tone {
  switch (s) {
    case "critical":
    case "high":
      return "bad";
    case "medium":
      return "warn";
    case "low":
      return "info";
    default:
      return "ok";
  }
}

export function Stat({ label, value, sub, className }: { label: string; value: ReactNode; sub?: ReactNode; className?: string }) {
  return (
    <div className={clsx("rounded-lg bg-slate-50 px-3 py-2", className)}>
      <div className="text-xs text-slate-500">{label}</div>
      <div className="num text-sm font-semibold text-slate-900">{value}</div>
      {sub && <div className="text-xs text-slate-500">{sub}</div>}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-sm text-slate-500">
      <Loader2 className="h-4 w-4 animate-spin" /> {label ?? "Laden…"}
    </div>
  );
}

export function Empty({ title, children, icon }: { title: string; children?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
      {icon}
      <div className="font-medium text-slate-800">{title}</div>
      {children && <div className="max-w-md text-sm text-slate-500">{children}</div>}
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error);
  return <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">Er ging iets mis: {msg}</div>;
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-0 sm:items-center sm:p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={clsx("max-h-[90vh] w-full overflow-y-auto rounded-t-2xl bg-white p-5 shadow-xl sm:rounded-2xl", wide ? "sm:max-w-3xl" : "sm:max-w-lg")}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button onClick={onClose} className="rounded p-1 text-slate-500 hover:bg-slate-100" aria-label="Sluiten">
            <X className="h-5 w-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
      <input type="checkbox" className="h-4 w-4 rounded border-slate-300 accent-brand-700" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}

export function Meter({ value, className }: { value: number | null | undefined; className?: string }) {
  const v = Math.max(0, Math.min(1, value ?? 0));
  const color = v >= 0.7 ? "bg-emerald-500" : v >= 0.45 ? "bg-amber-500" : "bg-rose-500";
  return (
    <div className={clsx("h-1.5 w-full overflow-hidden rounded-full bg-slate-200", className)}>
      <div className={clsx("h-full rounded-full", color)} style={{ width: `${v * 100}%` }} />
    </div>
  );
}
