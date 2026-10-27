import clsx from "clsx";
import { ChevronDown, X } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import type { Meta, SearchFilters } from "../lib/types";
import { Toggle } from "./ui";

type Setter = (patch: Partial<SearchFilters>) => void;

function Group({ title, children, defaultOpen = true }: { title: string; children: ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-slate-200 py-3 last:border-0">
      <button className="flex w-full items-center justify-between text-left text-sm font-medium text-slate-800" onClick={() => setOpen((o) => !o)}>
        {title}
        <ChevronDown className={clsx("h-4 w-4 text-slate-400 transition", open && "rotate-180")} />
      </button>
      {open && <div className="mt-2.5 space-y-2">{children}</div>}
    </div>
  );
}

function Chips({ options, value, onChange }: { options: Record<string, string>; value: string[] | undefined; onChange: (v: string[]) => void }) {
  const sel = value ?? [];
  return (
    <div className="flex flex-wrap gap-1.5">
      {Object.entries(options).map(([k, label]) => {
        const active = sel.includes(k);
        return (
          <button
            key={k}
            onClick={() => onChange(active ? sel.filter((x) => x !== k) : [...sel, k])}
            className={clsx(
              "rounded-full border px-2.5 py-1 text-xs",
              active ? "border-brand-600 bg-brand-50 text-brand-800" : "border-slate-200 bg-white text-slate-600 hover:border-slate-300",
            )}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

function NumberInput({ value, onChange, placeholder, step }: { value: number | null | undefined; onChange: (v: number | null) => void; placeholder: string; step?: number }) {
  return (
    <input
      type="number"
      inputMode="numeric"
      step={step}
      className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
      placeholder={placeholder}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
    />
  );
}

function Range({ label, min, max, onMin, onMax, step }: { label?: string; min: number | null | undefined; max: number | null | undefined; onMin: (v: number | null) => void; onMax: (v: number | null) => void; step?: number }) {
  return (
    <div>
      {label && <div className="mb-1 text-xs text-slate-500">{label}</div>}
      <div className="flex items-center gap-2">
        <NumberInput value={min} onChange={onMin} placeholder="van" step={step} />
        <span className="text-slate-400">–</span>
        <NumberInput value={max} onChange={onMax} placeholder="tot" step={step} />
      </div>
    </div>
  );
}

function ModelPicker({ meta, filters, set }: { meta: Meta; filters: SearchFilters; set: Setter }) {
  const [make, setMake] = useState("");
  const makeDef = useMemo(() => meta.catalog.find((m) => m.slug === make), [meta, make]);
  const selectedModels = filters.models ?? [];
  const selectedMakes = filters.makes ?? [];
  const label = (mm: string) => {
    const [mk, md] = mm.split("/");
    const mkDef = meta.catalog.find((m) => m.slug === mk);
    const mdDef = mkDef?.models.find((m) => m.slug === md);
    return `${mkDef?.name ?? mk} ${mdDef?.name ?? md ?? ""}`.trim();
  };
  return (
    <div className="space-y-2">
      <select
        className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm"
        value={make}
        onChange={(e) => setMake(e.target.value)}
        aria-label="Merk"
      >
        <option value="">Kies een merk…</option>
        {meta.catalog.map((m) => (
          <option key={m.slug} value={m.slug}>
            {m.name}
          </option>
        ))}
      </select>
      {makeDef && (
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => set({ makes: selectedMakes.includes(makeDef.slug) ? selectedMakes : [...selectedMakes, makeDef.slug] })}
            className="rounded-full border border-dashed border-slate-300 px-2.5 py-1 text-xs text-slate-600 hover:border-brand-500"
          >
            Alle {makeDef.name}
          </button>
          {makeDef.models.map((md) => {
            const key = `${makeDef.slug}/${md.slug}`;
            const active = selectedModels.includes(key);
            return (
              <button
                key={key}
                onClick={() => set({ models: active ? selectedModels.filter((x) => x !== key) : [...selectedModels, key] })}
                className={clsx(
                  "rounded-full border px-2.5 py-1 text-xs",
                  active ? "border-brand-600 bg-brand-50 text-brand-800" : "border-slate-200 bg-white text-slate-600 hover:border-slate-300",
                )}
              >
                {md.name}
              </button>
            );
          })}
        </div>
      )}
      {(selectedModels.length > 0 || selectedMakes.length > 0) && (
        <div className="flex flex-wrap gap-1.5">
          {selectedMakes.map((m) => (
            <span key={m} className="inline-flex items-center gap-1 rounded-full bg-brand-700 px-2.5 py-1 text-xs text-white">
              {meta.catalog.find((x) => x.slug === m)?.name ?? m} (alle)
              <button onClick={() => set({ makes: selectedMakes.filter((x) => x !== m) })} aria-label="Verwijder"><X className="h-3 w-3" /></button>
            </span>
          ))}
          {selectedModels.map((m) => (
            <span key={m} className="inline-flex items-center gap-1 rounded-full bg-brand-700 px-2.5 py-1 text-xs text-white">
              {label(m)}
              <button onClick={() => set({ models: selectedModels.filter((x) => x !== m) })} aria-label="Verwijder"><X className="h-3 w-3" /></button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Filters({ meta, filters, set, reset }: { meta: Meta; filters: SearchFilters; set: Setter; reset: () => void }) {
  return (
    <div className="text-sm">
      <div className="flex items-center justify-between pb-2">
        <h2 className="font-semibold text-slate-900">Filters</h2>
        <button onClick={reset} className="text-xs text-brand-700 hover:underline">Alles wissen</button>
      </div>
      <Group title="Merk & model">
        <ModelPicker meta={meta} filters={filters} set={set} />
      </Group>
      <Group title="Prijs, km & bouwjaar">
        <Range label="Prijs (€)" min={filters.price_min} max={filters.price_max} onMin={(v) => set({ price_min: v })} onMax={(v) => set({ price_max: v })} step={500} />
        <Range label="Kilometerstand" min={filters.km_min} max={filters.km_max} onMin={(v) => set({ km_min: v })} onMax={(v) => set({ km_max: v })} step={5000} />
        <Range label="Bouwjaar" min={filters.year_min} max={filters.year_max} onMin={(v) => set({ year_min: v })} onMax={(v) => set({ year_max: v })} />
        <div>
          <div className="mb-1 text-xs text-slate-500">Minimaal onder marktwaarde (%)</div>
          <NumberInput value={filters.min_deal_pct} onChange={(v) => set({ min_deal_pct: v })} placeholder="bijv. 5" />
        </div>
      </Group>
      <Group title="Brandstof">
        <Chips options={meta.fuels} value={filters.fuels} onChange={(v) => set({ fuels: v })} />
      </Group>
      <Group title="Carrosserie & transmissie">
        <Chips options={Object.fromEntries(Object.entries(meta.bodies).filter(([k]) => !["bestelwagen", "pickup"].includes(k)))} value={filters.bodies} onChange={(v) => set({ bodies: v })} />
        <Chips options={meta.transmissions} value={filters.transmissions} onChange={(v) => set({ transmissions: v })} />
      </Group>
      <Group title="Praktisch" defaultOpen={false}>
        <Range label="Vermogen (kW)" min={filters.kw_min} max={filters.kw_max} onMin={(v) => set({ kw_min: v })} onMax={(v) => set({ kw_max: v })} />
        <div className="grid grid-cols-2 gap-2">
          <div>
            <div className="mb-1 text-xs text-slate-500">Min. zitplaatsen</div>
            <NumberInput value={filters.seats_min} onChange={(v) => set({ seats_min: v })} placeholder="5" />
          </div>
          <div>
            <div className="mb-1 text-xs text-slate-500">Trekgewicht geremd (kg)</div>
            <NumberInput value={filters.towing_min} onChange={(v) => set({ towing_min: v })} placeholder="1200" step={100} />
          </div>
          <div>
            <div className="mb-1 text-xs text-slate-500">Min. actieradius EV (km)</div>
            <NumberInput value={filters.range_min} onChange={(v) => set({ range_min: v })} placeholder="300" step={25} />
          </div>
          <div>
            <div className="mb-1 text-xs text-slate-500">Max. afstand (km)</div>
            <NumberInput value={filters.max_distance_km} onChange={(v) => set({ max_distance_km: v })} placeholder="50" step={10} />
          </div>
        </div>
        <div>
          <div className="mb-1 text-xs text-slate-500">Moet hebben</div>
          <Chips options={meta.options} value={filters.options} onChange={(v) => set({ options: v })} />
        </div>
        <div>
          <div className="mb-1 text-xs text-slate-500">Kleur</div>
          <Chips options={Object.fromEntries(meta.colours.map((c) => [c, c[0].toUpperCase() + c.slice(1)]))} value={filters.colours} onChange={(v) => set({ colours: v })} />
        </div>
      </Group>
      <Group title="Verkoper" defaultOpen={false}>
        <Chips options={{ dealer: "Dealer", private: "Particulier" }} value={filters.seller_types} onChange={(v) => set({ seller_types: v })} />
        <Toggle checked={!!filters.bovag_only} onChange={(v) => set({ bovag_only: v })} label="Alleen BOVAG" />
        <Toggle checked={!!filters.warranty_only} onChange={(v) => set({ warranty_only: v })} label="Met garantie" />
        <Chips
          options={Object.fromEntries(meta.sources.filter((s) => s.enabled).map((s) => [s.name, s.label]))}
          value={filters.sources}
          onChange={(v) => set({ sources: v })}
        />
      </Group>
      <Group title="Zekerheid">
        <Toggle checked={!!filters.hide_nap_issues} onChange={(v) => set({ hide_nap_issues: v })} label="Verberg onlogische NAP" />
        <Toggle checked={!!filters.hide_open_recall} onChange={(v) => set({ hide_open_recall: v })} label="Verberg open terugroepacties" />
        <Toggle checked={!!filters.hide_import} onChange={(v) => set({ hide_import: v })} label="Verberg importauto's" />
        <Toggle checked={!!filters.hide_high_flags} onChange={(v) => set({ hide_high_flags: v })} label="Verberg ernstige rode vlaggen" />
        <Toggle checked={!!filters.hide_battery_lease} onChange={(v) => set({ hide_battery_lease: v })} label="Verberg huuraccu's" />
      </Group>
    </div>
  );
}
