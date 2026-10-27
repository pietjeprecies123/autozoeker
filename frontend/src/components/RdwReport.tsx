import { CheckCircle2, CircleAlert, ShieldAlert, XCircle } from "lucide-react";
import type { ReactNode } from "react";
import { date, daysUntil, euro, num } from "../lib/format";
import type { Vehicle } from "../lib/types";
import { Badge } from "./ui";

function Row({ label, children, status }: { label: string; children: ReactNode; status?: "ok" | "warn" | "bad" }) {
  const Icon = status === "ok" ? CheckCircle2 : status === "warn" ? CircleAlert : status === "bad" ? XCircle : null;
  const colour = status === "ok" ? "text-emerald-600" : status === "warn" ? "text-amber-600" : "text-rose-600";
  return (
    <div className="flex items-start justify-between gap-4 border-b border-slate-100 py-2 text-sm last:border-0">
      <span className="text-slate-500">{label}</span>
      <span className="flex items-center gap-1.5 text-right font-medium text-slate-900">
        {children}
        {Icon && <Icon className={`h-4 w-4 shrink-0 ${colour}`} />}
      </span>
    </div>
  );
}

const yesNo = (v: boolean | null | undefined) => (v == null ? "–" : v ? "Ja" : "Nee");

export default function RdwReport({ v }: { v: Vehicle }) {
  if (!v.found) {
    return <div className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">Dit kenteken komt niet voor in het RDW-register.</div>;
  }
  const apkDays = daysUntil(v.apk_expiry);
  const nap = (v.odometer_judgement || "").toLowerCase();
  return (
    <div className="space-y-4">
      {v.is_demo && <Badge tone="demo">DEMO-gegevens – geen echte RDW-registratie</Badge>}
      <div className="grid gap-x-8 md:grid-cols-2">
        <div>
          <Row label="Merk / handelsbenaming">{[v.make, v.trade_name].filter(Boolean).join(" ") || "–"}</Row>
          <Row label="Eerste toelating">{date(v.first_admission)}</Row>
          <Row label="Eerste registratie NL" status={v.is_import ? "warn" : "ok"}>
            {date(v.first_nl_registration)} {v.is_import && <Badge tone="warn">import</Badge>}
          </Row>
          <Row label="APK geldig tot" status={apkDays == null ? undefined : apkDays < 0 ? "bad" : apkDays < 60 ? "warn" : "ok"}>
            {date(v.apk_expiry)}
            {apkDays != null && apkDays >= 0 && <span className="text-xs font-normal text-slate-500">({apkDays} dagen)</span>}
          </Row>
          <Row label="Tellerstand (NAP)" status={nap.startsWith("logisch") ? "ok" : nap.includes("onlogisch") ? "bad" : "warn"}>
            {v.odometer_judgement || "Geen oordeel"}
          </Row>
          {v.odometer_explanation && <p className="pb-2 text-xs text-slate-500">{v.odometer_explanation}</p>}
          <Row label="Openstaande terugroepactie" status={v.open_recall ? "bad" : "ok"}>{yesNo(v.open_recall)}</Row>
          <Row label="Ex-taxi" status={v.taxi ? "warn" : undefined}>{yesNo(v.taxi)}</Row>
          <Row label="Geëxporteerd" status={v.export ? "bad" : undefined}>{yesNo(v.export)}</Row>
          <Row label="WAM-verzekerd">{yesNo(v.insured)}</Row>
        </div>
        <div>
          <Row label="Catalogusprijs (nieuw)">{euro(v.catalog_price)}</Row>
          <Row label="Brandstof">{v.fuel ?? "–"}</Row>
          <Row label="Vermogen">{v.power_kw ? `${Math.round(v.power_kw)} kW` : "–"}</Row>
          <Row label="Verbruik (officieel)">
            {v.consumption_l_100km ? `${v.consumption_l_100km} l/100 km` : v.consumption_kwh_100km ? `${v.consumption_kwh_100km} kWh/100 km` : "–"}
          </Row>
          {v.range_km && <Row label="Actieradius (WLTP)">{v.range_km} km</Row>}
          <Row label="CO₂">{v.co2_g_km ? `${Math.round(v.co2_g_km)} g/km` : "–"}</Row>
          <Row label="Massa leeg / rijklaar">{v.mass_empty ? `${num(v.mass_empty)} / ${num(v.mass_ready)} kg` : "–"}</Row>
          <Row label="Trekgewicht geremd / ongeremd">{v.towing_braked != null ? `${num(v.towing_braked)} / ${num(v.towing_unbraked)} kg` : "–"}</Row>
          <Row label="Zitplaatsen">{v.seats ?? "–"}</Row>
          {v.energy_label && <Row label="Energielabel">{v.energy_label}</Row>}
          {v.emission_class && <Row label="Emissieklasse">{v.emission_class}</Row>}
        </div>
      </div>
      {v.recalls.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold">Terugroepacties</h3>
          <div className="space-y-2">
            {v.recalls.map((r) => (
              <div key={r.referentiecode_rdw} className="rounded-lg border border-slate-200 p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={r.open ? "bad" : "good"}>{r.open ? <ShieldAlert className="h-3 w-3" /> : <CheckCircle2 className="h-3 w-3" />}{r.status}</Badge>
                  <span className="text-xs text-slate-500">{r.referentiecode_rdw}</span>
                  {r.publicatiedatum && <span className="text-xs text-slate-500">{date(r.publicatiedatum)}</span>}
                </div>
                {(r.titel || r.omschrijving_defect) && <p className="mt-1 text-slate-700">{r.titel ? `${r.titel}: ` : ""}{r.omschrijving_defect}</p>}
                {r.herstel && <p className="mt-1 text-xs text-slate-500">Herstel: {r.herstel}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
      {v.apk_defects.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold">Gebreken bij eerdere APK-keuringen</h3>
          <table className="w-full text-sm">
            <tbody>
              {v.apk_defects.slice(0, 15).map((d, i) => (
                <tr key={i} className="border-b border-slate-100 last:border-0">
                  <td className="num py-1.5 pr-3 text-slate-500">{date(d.datum)}</td>
                  <td className="py-1.5">{d.omschrijving || d.code}</td>
                  <td className="num py-1.5 text-right text-slate-500">{d.aantal}×</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-xs text-slate-400">Bron: RDW Open Data · opgehaald {date(v.fetched_at)}</p>
    </div>
  );
}
