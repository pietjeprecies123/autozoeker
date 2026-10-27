import { useQuery } from "@tanstack/react-query";
import { BarChart3, Flame } from "lucide-react";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ListingRow } from "../components/car";
import { Card, Empty, ErrorBox, Section, Spinner, Stat } from "../components/ui";
import { api } from "../lib/api";
import { euro, km, pct } from "../lib/format";
import { useApp } from "../lib/store";

const k = (v: number) => `€${Math.round(v / 1000)}k`;

function Insights({ make, model, fuel }: { make: string; model: string; fuel: string }) {
  const navigate = useNavigate();
  const q = useQuery({ queryKey: ["insights", make, model, fuel], queryFn: () => api.insights(make, model || undefined, fuel || undefined) });
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBox error={q.error} />;
  const d = q.data;
  if (!d.active) return <Empty title="Geen aanbod gevonden">Kies een ander model of verruim de filters.</Empty>;
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
        <Stat label="Te koop" value={d.active} />
        <Stat label="Recent verkocht/offline" value={d.sold_recently} />
        <Stat label="Mediaanprijs" value={euro(d.median_price)} />
        <Stat label="Mediaan km" value={km(d.median_km)} />
        <Stat label="Dagen tot verkoop (mediaan)" value={d.median_days_to_sale ?? "–"} />
        <Stat label="Waardeverlies per jaar" value={d.yearly_value_loss_pct != null ? `${String(d.yearly_value_loss_pct).replace(".", ",")}%` : "–"} sub={d.share_price_drop != null ? `${pct(d.share_price_drop)} verlaagde prijs` : undefined} />
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Section title="Prijs vs. kilometerstand">
          {d.trend && <p className="mb-2 text-sm text-slate-600">Elke 10.000 km extra kost gemiddeld <b>{String(Math.abs(d.trend.per_10k_km_pct)).replace(".", ",")}%</b> van de waarde.</p>}
          <div className="h-72">
            <ResponsiveContainer>
              <ComposedChart margin={{ left: 10, right: 10, bottom: 10 }}>
                <CartesianGrid stroke="#f1f5f9" />
                <XAxis type="number" dataKey="km" tickFormatter={(v) => `${Math.round(v / 1000)}k`} fontSize={11} domain={["auto", "auto"]} />
                <YAxis type="number" dataKey="price" tickFormatter={k} fontSize={11} width={45} domain={["auto", "auto"]} />
                <Tooltip formatter={(v, n) => (n === "price" ? euro(Number(v)) : km(Number(v)))} />
                <Scatter data={d.scatter} fill="#0d9488" fillOpacity={0.45} cursor="pointer" onClick={(p: any) => navigate(`/auto/${p.payload?.id ?? p.id}`)} />
                {d.trend && <Line data={d.trend.line} dataKey="price" stroke="#e11d48" strokeWidth={2} dot={false} isAnimationActive={false} />}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </Section>
        <Section title="Prijs per bouwjaar">
          <div className="h-72">
            <ResponsiveContainer>
              <ComposedChart data={d.per_year} margin={{ left: 10, right: 10 }}>
                <CartesianGrid stroke="#f1f5f9" />
                <XAxis dataKey="year" fontSize={11} />
                <YAxis tickFormatter={k} fontSize={11} width={45} />
                <Tooltip formatter={(v) => euro(Number(v))} />
                <Bar dataKey="median" fill="#0f766e" radius={[4, 4, 0, 0]} name="mediaan" />
                <Line dataKey="p25" stroke="#94a3b8" dot={false} name="25%" />
                <Line dataKey="p75" stroke="#94a3b8" dot={false} name="75%" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </Section>
        <Section title="Prijsverdeling">
          <div className="h-60">
            <ResponsiveContainer>
              <BarChart data={d.histogram} margin={{ left: 10, right: 10 }}>
                <CartesianGrid stroke="#f1f5f9" />
                <XAxis dataKey="from" tickFormatter={k} fontSize={11} />
                <YAxis fontSize={11} allowDecimals={false} width={30} />
                <Tooltip labelFormatter={(v) => `vanaf ${euro(Number(v))}`} />
                <Bar dataKey="count" fill="#14b8a6" radius={[3, 3, 0, 0]} name="aantal" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Section>
        <Section title="Aanbod per week">
          <div className="h-60">
            <ResponsiveContainer>
              <AreaChart data={d.supply} margin={{ left: 10, right: 10 }}>
                <CartesianGrid stroke="#f1f5f9" />
                <XAxis dataKey="week" fontSize={11} />
                <YAxis fontSize={11} width={35} />
                <Tooltip />
                <Area dataKey="count" stroke="#0f766e" fill="#99f6e4" name="te koop" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Section>
      </div>
      {d.deals?.length > 0 && (
        <Section title="Beste koopjes van dit model" icon={<Flame className="h-5 w-5 text-orange-500" />}>
          <div className="space-y-3">{d.deals.map((l: any) => <ListingRow key={l.id} l={l} />)}</div>
        </Section>
      )}
    </div>
  );
}

export default function MarketPage() {
  const { meta } = useApp();
  const [params, setParams] = useSearchParams();
  const make = params.get("make") || "";
  const model = params.get("model") || "";
  const [fuel, setFuel] = useState("");
  const deals = useQuery({ queryKey: ["deals"], queryFn: api.deals, enabled: !make });
  if (!meta) return <Spinner />;
  const makeDef = meta.catalog.find((m) => m.slug === make);
  return (
    <div className="space-y-5">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-bold"><BarChart3 className="h-5 w-5 text-brand-700" />Marktinzicht</h1>
        <p className="text-sm text-slate-600">Prijzen, afschrijving, aanbod en verkoopsnelheid per model, op basis van alle advertenties die Autozoeker heeft gezien.</p>
      </div>
      <Card className="flex flex-wrap gap-2 p-4">
        <select value={make} onChange={(e) => setParams(e.target.value ? { make: e.target.value } : {})} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" aria-label="Merk">
          <option value="">Kies merk…</option>
          {meta.catalog.map((m) => <option key={m.slug} value={m.slug}>{m.name}</option>)}
        </select>
        <select
          value={model}
          onChange={(e) => setParams(e.target.value ? { make, model: e.target.value } : { make })}
          disabled={!makeDef}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          aria-label="Model"
        >
          <option value="">Alle modellen</option>
          {makeDef?.models.map((m) => <option key={m.slug} value={m.slug}>{m.name}</option>)}
        </select>
        <select value={fuel} onChange={(e) => setFuel(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" aria-label="Brandstof">
          <option value="">Alle brandstoffen</option>
          {Object.entries(meta.fuels).map(([k2, v]) => <option key={k2} value={k2}>{v}</option>)}
        </select>
      </Card>
      {make ? (
        <Insights make={make} model={model} fuel={fuel} />
      ) : (
        <Section title="Beste deals vandaag" icon={<Flame className="h-5 w-5 text-orange-500" />}>
          <p className="mb-3 text-sm text-slate-600">Auto's die het meest onder de geschatte marktwaarde staan (alleen schattingen met redelijke betrouwbaarheid, zonder ernstige rode vlaggen).</p>
          {deals.isLoading && <Spinner />}
          <div className="space-y-3">{deals.data?.items.map((l) => <ListingRow key={l.id} l={l} />)}</div>
        </Section>
      )}
    </div>
  );
}
