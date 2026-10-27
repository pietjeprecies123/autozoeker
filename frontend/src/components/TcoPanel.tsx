import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { useState } from "react";
import { api } from "../lib/api";
import { euro } from "../lib/format";
import { useApp } from "../lib/store";
import { Spinner } from "./ui";

const LABELS: Record<string, string> = {
  brandstof_energie: "Brandstof / laden",
  wegenbelasting: "Wegenbelasting (schatting)",
  onderhoud_banden: "Onderhoud & banden",
  verzekering: "Verzekering",
  afschrijving: "Afschrijving",
};
const COLOURS: Record<string, string> = {
  brandstof_energie: "bg-sky-500",
  wegenbelasting: "bg-violet-500",
  onderhoud_banden: "bg-amber-500",
  verzekering: "bg-slate-500",
  afschrijving: "bg-rose-500",
};

const ENERGY_FIELDS = [
  ["euro95_per_l", "Euro95 €/l"],
  ["diesel_per_l", "Diesel €/l"],
  ["lpg_per_l", "LPG €/l"],
  ["kwh_home", "Thuisladen €/kWh"],
  ["kwh_public", "Publiek laden €/kWh"],
  ["public_share", "Deel publiek laden (0–1)"],
] as const;
type Energy = Partial<Record<(typeof ENERGY_FIELDS)[number][0], number>>;

function loadEnergy(): Energy {
  try {
    return JSON.parse(localStorage.getItem("az.energy") || "{}");
  } catch {
    return {};
  }
}

function Field({ label, value, onChange, step, placeholder }: { label: string; value: number | ""; onChange: (v: number | "") => void; step?: number; placeholder?: string }) {
  return (
    <label className="block text-xs text-slate-500">
      {label}
      <input
        type="number"
        step={step}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))}
        className="mt-1 w-full rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm text-slate-900"
      />
    </label>
  );
}

export default function TcoPanel({ listingId }: { listingId: number }) {
  const { profileId } = useApp();
  const [kmYear, setKmYear] = useState<number | "">(13000);
  const [years, setYears] = useState<number | "">(3);
  const [insurance, setInsurance] = useState<number | "">("");
  const [mrb, setMrb] = useState<number | "">("");
  const [energy, setEnergy] = useState<Energy>(loadEnergy);
  const setEnergyField = (key: keyof Energy, v: number | "") => {
    const next = { ...energy };
    if (v === "") delete next[key];
    else next[key] = v;
    setEnergy(next);
    try {
      localStorage.setItem("az.energy", JSON.stringify(next));
    } catch {
      /* storage unavailable: keep it for this page only */
    }
  };
  const input = {
    ...energy,
    km_per_year: kmYear || 13000,
    years: years || 3,
    insurance_month: insurance === "" ? null : insurance,
    mrb_quarter_override: mrb === "" ? null : mrb,
  };
  const q = useQuery({ queryKey: ["tco", listingId, input, profileId], queryFn: () => api.tco(listingId, input, profileId), placeholderData: keepPreviousData });
  const t = q.data;
  const total = t?.monthly.totaal ?? 0;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="Km per jaar" value={kmYear} onChange={setKmYear} step={1000} />
        <Field label="Jaren in bezit" value={years} onChange={setYears} />
        <Field label="Verzekering €/mnd" value={insurance} onChange={setInsurance} />
        <Field label="Wegenbelasting €/kwartaal" value={mrb} onChange={setMrb} />
      </div>
      {!t ? (
        <Spinner />
      ) : (
        <>
          <div className="flex items-end justify-between">
            <div>
              <div className="num text-3xl font-bold text-slate-900">{euro(total)}<span className="text-base font-normal text-slate-500"> /maand</span></div>
              <div className="num text-sm text-slate-500">≈ {t.per_km != null ? `€ ${t.per_km.toFixed(2).replace(".", ",")}` : "–"} per km · verwachte restwaarde na {t.years} jaar {euro(t.resale_value)}</div>
            </div>
          </div>
          <div className="flex h-3 overflow-hidden rounded-full bg-slate-100">
            {Object.entries(t.monthly)
              .filter(([k]) => k !== "totaal")
              .map(([k, v]) => (
                <div key={k} className={COLOURS[k]} style={{ width: `${total ? (v / total) * 100 : 0}%` }} title={`${LABELS[k]}: ${euro(v)}`} />
              ))}
          </div>
          <div className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
            {Object.entries(t.monthly)
              .filter(([k]) => k !== "totaal")
              .map(([k, v]) => (
                <div key={k} className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-slate-600"><span className={`h-2.5 w-2.5 rounded-sm ${COLOURS[k]}`} />{LABELS[k]}</span>
                  <span className="num font-medium">{euro(v)}</span>
                </div>
              ))}
          </div>
          <div className="space-y-1 text-xs text-slate-500">
            <div>
              Verbruik: {t.consumption.real_l_100km ? `${t.consumption.real_l_100km} l/100 km` : ""}
              {t.consumption.real_kwh_100km ? ` ${t.consumption.real_kwh_100km} kWh/100 km` : ""} (praktijk, {t.consumption.source})
            </div>
            <div>
              {t.mrb.basis}.{" "}
              <a href={t.mrb.exact_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 text-brand-700 hover:underline">
                Exact bedrag bij de Belastingdienst <ExternalLink className="h-3 w-3" />
              </a>
            </div>
            {t.notes.map((n) => <div key={n}>{n}</div>)}
          </div>
          <details className="text-sm">
            <summary className="cursor-pointer text-brand-700">Energieprijzen aanpassen</summary>
            <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3">
              {ENERGY_FIELDS.map(([key, label]) => (
                <Field key={key} label={label} step={0.01} value={energy[key] ?? ""} placeholder={String(t.inputs[key] ?? "")}
                  onChange={(v) => setEnergyField(key, v)} />
              ))}
            </div>
            <p className="mt-1 text-xs text-slate-500">Wordt in deze browser onthouden en geldt voor alle auto's.</p>
          </details>
        </>
      )}
    </div>
  );
}
