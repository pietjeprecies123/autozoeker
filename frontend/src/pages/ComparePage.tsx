import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CarImage, DealBadge, ScoreRing } from "../components/car";
import { Badge, Empty, ErrorBox, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { date, euro, km } from "../lib/format";
import { useApp } from "../lib/store";

type Item = Awaited<ReturnType<typeof api.compare>>["items"][number];

export default function ComparePage() {
  const [params] = useSearchParams();
  const { profileId, toggleCompare } = useApp();
  const ids = (params.get("ids") || "").split(",").map(Number).filter(Boolean);
  const q = useQuery({ queryKey: ["compare", ids, profileId], queryFn: () => api.compare(ids, profileId), enabled: ids.length > 0 });
  if (!ids.length) return <Empty title="Niets om te vergelijken">Klik op het vergelijk-icoon bij een auto (max. 4).</Empty>;
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBox error={q.error} />;
  const items = q.data.items;

  const best = (fn: (i: Item) => number | null | undefined, lower = true) => {
    const vals = items.map(fn).filter((v): v is number => v != null);
    if (!vals.length) return null;
    return lower ? Math.min(...vals) : Math.max(...vals);
  };
  const row = (label: string, render: (i: Item) => ReactNode, score?: (i: Item) => number | null | undefined, lower = true) => {
    const b = score ? best(score, lower) : null;
    return (
      <tr className="border-t border-slate-100">
        <th className="sticky left-0 bg-white py-2 pr-4 text-left text-xs font-medium text-slate-500">{label}</th>
        {items.map((i) => (
          <td key={i.id} className={clsx("num px-3 py-2 text-sm", score && b != null && score(i) === b && "font-semibold text-emerald-700")}>
            {render(i)}
          </td>
        ))}
      </tr>
    );
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Vergelijken</h1>
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white p-4">
        <table className="w-full min-w-[640px]">
          <thead>
            <tr>
              <th className="w-44" />
              {items.map((i) => (
                <th key={i.id} className="px-3 pb-3 text-left align-top">
                  <div className="relative h-28 overflow-hidden rounded-lg bg-slate-100">
                    <CarImage listing={i} />
                    <button onClick={() => toggleCompare(i.id)} className="absolute right-1 top-1 rounded bg-white/90 p-1" aria-label="Verwijder">
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <Link to={`/auto/${i.id}`} className="mt-2 line-clamp-2 block text-sm font-semibold text-slate-900 hover:text-brand-700">{i.title}</Link>
                  <div className="mt-1 flex items-center gap-2">
                    <ScoreRing value={i.match} size={36} />
                    {i.is_demo && <Badge tone="demo">DEMO</Badge>}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {row("Vraagprijs", (i) => euro(i.price_eur), (i) => i.price_eur)}
            {row("Marktwaarde", (i) => euro(i.predicted_price))}
            {row("Prijs t.o.v. markt", (i) => <DealBadge deal={i.deal_score} />, (i) => i.deal_score, false)}
            {row("Match-score", (i) => i.match ?? "–", (i) => i.match, false)}
            {row("Bouwjaar", (i) => i.year ?? "–", (i) => i.year, false)}
            {row("Kilometerstand", (i) => km(i.mileage_km), (i) => i.mileage_km)}
            {row("Brandstof", (i) => i.fuel_label ?? "–")}
            {row("Vermogen", (i) => (i.power_kw ? `${i.power_kw} kW` : "–"), (i) => i.power_kw, false)}
            {row("Transmissie", (i) => i.transmission ?? "–")}
            {row("Kosten p/mnd (totaal)", (i) => euro(i.tco.monthly.totaal), (i) => i.tco.monthly.totaal)}
            {row("· brandstof/laden", (i) => euro(i.tco.monthly.brandstof_energie), (i) => i.tco.monthly.brandstof_energie)}
            {row("· wegenbelasting", (i) => euro(i.tco.monthly.wegenbelasting), (i) => i.tco.monthly.wegenbelasting)}
            {row("· afschrijving", (i) => euro(i.tco.monthly.afschrijving), (i) => i.tco.monthly.afschrijving)}
            {row("Kosten per km", (i) => (i.tco.per_km != null ? `€ ${i.tco.per_km.toFixed(2).replace(".", ",")}` : "–"), (i) => i.tco.per_km)}
            {row("APK tot", (i) => date(i.vehicle?.apk_expiry))}
            {row("NAP", (i) => i.vehicle?.odometer_judgement ?? "–")}
            {row("Trekgewicht", (i) => (i.vehicle?.towing_braked != null ? `${i.vehicle.towing_braked} kg` : "–"), (i) => i.vehicle?.towing_braked, false)}
            {row("Aandachtspunten", (i) => (i.issues.length ? `${i.issues.length} (≈ ${euro(i.issue_cost)} risico)` : "geen bekend"), (i) => i.issue_cost)}
            {row("Rode vlaggen", (i) => i.red_flags.filter((f) => f.severity !== "info").map((f) => f.title).join(", ") || "–", (i) => i.red_flags.filter((f) => f.severity !== "info").length)}
            {row("Verkoper", (i) => `${i.seller_type === "dealer" ? "Dealer" : "Particulier"}${i.seller_bovag ? " · BOVAG" : ""}${i.warranty_months ? ` · ${i.warranty_months} mnd` : ""}`)}
            {row("Afstand", (i) => (i.distance_km != null ? `${Math.round(i.distance_km)} km` : "–"), (i) => i.distance_km)}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-500">Groen = beste waarde in de rij. Kosten bij 13.000 km/jaar, 3 jaar bezit, standaard verzekering.</p>
    </div>
  );
}
