const nf = new Intl.NumberFormat("nl-NL");

export const euro = (v: number | null | undefined) => (v == null ? "–" : `€ ${nf.format(Math.round(v))}`);
export const km = (v: number | null | undefined) => (v == null ? "–" : `${nf.format(Math.round(v))} km`);
export const num = (v: number | null | undefined) => (v == null ? "–" : nf.format(v));
export const pct = (v: number | null | undefined, digits = 0) =>
  v == null ? "–" : `${(v * 100).toFixed(digits).replace(".", ",")}%`;

export const date = (v: string | null | undefined) => {
  if (!v) return "–";
  const d = new Date(v);
  return isNaN(d.getTime()) ? v : d.toLocaleDateString("nl-NL", { day: "numeric", month: "short", year: "numeric" });
};

export const monthYear = (v: string | null | undefined) => {
  if (!v) return "–";
  const d = new Date(v);
  return isNaN(d.getTime()) ? v : d.toLocaleDateString("nl-NL", { month: "2-digit", year: "numeric" });
};

export const daysUntil = (v: string | null | undefined) => {
  if (!v) return null;
  const d = new Date(v);
  return Math.round((d.getTime() - Date.now()) / 86400000);
};

export function dealLabel(deal: number | null | undefined): { text: string; tone: "good" | "ok" | "bad" | "none" } {
  if (deal == null) return { text: "Geen schatting", tone: "none" };
  const p = Math.round(deal * 100);
  if (p >= 8) return { text: `${p}% onder marktwaarde`, tone: "good" };
  if (p >= 3) return { text: `${p}% onder marktwaarde`, tone: "good" };
  if (p > -3) return { text: "Marktconform", tone: "ok" };
  return { text: `${-p}% boven marktwaarde`, tone: "bad" };
}

export const severityOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
