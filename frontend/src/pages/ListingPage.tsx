import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import {
  AlertTriangle,
  BadgeCheck,
  Battery,
  Bot,
  ClipboardCheck,
  ExternalLink,
  FileSearch,
  GitCompare,
  Handshake,
  Heart,
  LineChart as LineIcon,
  ShieldCheck,
  ThumbsDown,
  ThumbsUp,
  Wallet,
  Wrench,
} from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CarImage, DealBadge, ScoreRing } from "../components/car";
import IssueCard from "../components/IssueCard";
import RdwReport from "../components/RdwReport";
import TcoPanel from "../components/TcoPanel";
import { Badge, Button, ErrorBox, Meter, Section, Spinner, Stat, severityTone } from "../components/ui";
import ValueBand from "../components/ValueBand";
import { api } from "../lib/api";
import { date, euro, km, monthYear } from "../lib/format";
import { useApp } from "../lib/store";
import type { ListingDetail } from "../lib/types";

function ScoreBreakdown({ l }: { l: ListingDetail }) {
  const { meta } = useApp();
  const rows: [string, number | null][] = [
    ["deal", l.components.deal],
    ["km", l.components.km],
    ["health", l.components.health],
    ["issues", l.components.issues],
    ["seller", l.components.seller],
  ];
  return (
    <div className="space-y-2.5">
      {rows.map(([k, v]) => (
        <div key={k}>
          <div className="mb-1 flex justify-between text-xs">
            <span className="text-slate-600">{meta?.weight_labels[k] ?? k}</span>
            <span className="num text-slate-500">{v == null ? "–" : Math.round(v * 100)}</span>
          </div>
          <Meter value={v} />
        </div>
      ))}
      {l.health_notes.length > 0 && <p className="text-xs text-slate-500">RDW: {l.health_notes.join(" · ")}</p>}
    </div>
  );
}

function AdScan({ id }: { id: number }) {
  const { meta } = useApp();
  const scan = useMutation({ mutationFn: (force: boolean) => api.adScan(id, force) });
  if (!meta?.ai_enabled) {
    return <p className="text-sm text-slate-500">Stel <code>ANTHROPIC_API_KEY</code> in om advertenties door Claude te laten doorlezen op verborgen signalen.</p>;
  }
  return (
    <div className="space-y-3 text-sm">
      {!scan.data && (
        <Button variant="secondary" onClick={() => scan.mutate(false)} disabled={scan.isPending}>
          <Bot className="h-4 w-4" /> {scan.isPending ? "Claude leest mee…" : "Laat Claude de advertentie lezen"}
        </Button>
      )}
      {scan.error && <ErrorBox error={scan.error} />}
      {scan.data && (
        <>
          <p className="text-slate-700">{scan.data.summary}</p>
          {scan.data.flags.map((f) => (
            <div key={f.title} className="flex gap-2">
              <Badge tone={severityTone(f.severity)}>{f.severity}</Badge>
              <div><span className="font-medium">{f.title}</span> <span className="text-slate-600">{f.detail}</span></div>
            </div>
          ))}
          {scan.data.positives.length > 0 && <p className="text-emerald-700">Pluspunten: {scan.data.positives.join(" · ")}</p>}
          {scan.data.questions.length > 0 && (
            <div>
              <div className="text-xs font-semibold uppercase text-brand-800">Extra vragen</div>
              <ul className="list-disc pl-5">{scan.data.questions.map((q) => <li key={q}>{q}</li>)}</ul>
            </div>
          )}
          <p className="text-xs text-slate-400">AI-analyse, controleer zelf. Kosten ≈ ${scan.data.cost_usd?.toFixed(3) ?? "?"}</p>
        </>
      )}
    </div>
  );
}

function Research({ make, model }: { make: string; model: string }) {
  const { meta } = useApp();
  const qc = useQueryClient();
  const research = useMutation({
    mutationFn: () => api.research(make, model),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["listing"] }),
  });
  if (!meta?.ai_enabled) {
    return (
      <p className="text-sm text-slate-500">
        Voor dit model staat (nog) niets in de samengestelde kennisbank. Met een <code>ANTHROPIC_API_KEY</code> kan Autozoeker bekende problemen op internet laten
        onderzoeken door Claude (eenmalig, ca. €0,25–0,35 per model).
      </p>
    );
  }
  return (
    <div className="space-y-2">
      <p className="text-sm text-slate-600">Voor dit model staat nog niets in de samengestelde kennisbank.</p>
      <Button variant="secondary" onClick={() => research.mutate()} disabled={research.isPending}>
        <FileSearch className="h-4 w-4" /> {research.isPending ? "Claude zoekt bronnen (±1 min)…" : "Onderzoek bekende problemen met AI"}
      </Button>
      {research.error && <ErrorBox error={research.error} />}
    </div>
  );
}

export default function ListingPage() {
  const { id } = useParams();
  const listingId = Number(id);
  const { profileId, compare, toggleCompare } = useApp();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["listing", listingId, profileId], queryFn: () => api.listing(listingId, profileId) });
  const [showDesc, setShowDesc] = useState(false);
  const watch = useMutation({
    mutationFn: async () => {
      const l = q.data!;
      if (l.watchlist) await api.deleteWatch(l.watchlist.id);
      else await api.addWatch(l.id, profileId);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["listing", listingId] });
      qc.invalidateQueries({ queryKey: ["watchlist"] });
    },
  });
  const feedback = useMutation({
    mutationFn: (v: number) => api.feedback(listingId, profileId!, v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["listing", listingId] }),
  });

  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBox error={q.error ?? "Niet gevonden"} />;
  const l = q.data;
  const inCompare = compare.includes(l.id);
  const flags = l.red_flags.filter((f) => f.severity !== "info");
  const infos = l.red_flags.filter((f) => f.severity === "info");

  return (
    <div className="space-y-5">
      <div className="text-sm text-slate-500">
        <Link to="/" className="hover:underline">Zoeken</Link> / {l.make_name} {l.model_name}
        {l.generation_name && <> / <Link to={`/aandachtspunten/${l.make}/${l.model}`} className="hover:underline">{l.generation_name}</Link></>}
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_380px]">
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <div className="grid sm:grid-cols-[minmax(0,300px)_1fr]">
            <div className="h-56 bg-slate-100 sm:h-full">
              <CarImage listing={l} />
            </div>
            <div className="space-y-3 p-5">
              <div className="flex flex-wrap gap-1.5">
                {l.is_demo ? <Badge tone="demo">DEMO</Badge> : <Badge tone="ok">{l.source_label}</Badge>}
                {l.status !== "active" && <Badge tone="bad">Offline sinds {date(l.removed_at)}</Badge>}
                {l.seller_bovag && <Badge tone="brand"><BadgeCheck className="h-3 w-3" />BOVAG</Badge>}
                {l.kenteken && <Link to={`/kenteken/${l.kenteken}`}><Badge tone="warn">{l.kenteken}</Badge></Link>}
              </div>
              <h1 className="text-xl font-bold text-slate-900">{l.title}</h1>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                <Stat label="Eerste toelating" value={monthYear(l.first_registration) || l.year} />
                <Stat label="Kilometerstand" value={km(l.mileage_km)} sub={l.expected_km ? `normaal ≈ ${km(l.expected_km)}` : undefined} />
                <Stat label="Brandstof" value={l.fuel_label ?? "–"} sub={l.battery_kwh ? `${l.battery_kwh} kWh accu` : undefined} />
                <Stat label="Transmissie" value={l.transmission === "automaat" ? "Automaat" : l.transmission ? "Handgeschakeld" : "–"} />
                <Stat label="Vermogen" value={l.power_kw ? `${l.power_kw} kW / ${l.power_pk} pk` : "–"} />
                <Stat label="Verkoper" value={l.seller_name ?? "–"} sub={`${l.seller_type === "dealer" ? "Dealer" : "Particulier"}${l.warranty_months ? ` · ${l.warranty_months} mnd garantie` : ""}`} />
                <Stat label="Locatie" value={l.city || (l.postcode ? `PC ${l.postcode}` : "–")} sub={l.distance_km != null ? `≈ ${Math.round(l.distance_km)} km rijden` : undefined} />
                <Stat label="Online" value={`${l.days_online ?? 0} dagen`} sub={l.price_drops ? `${l.price_drops}× verlaagd` : undefined} />
                <Stat label="Carrosserie" value={l.body_label ?? "–"} />
              </div>
              {l.option_labels.length > 0 && <div className="flex flex-wrap gap-1">{l.option_labels.map((o) => <Badge key={o} tone="ok">{o}</Badge>)}</div>}
            </div>
          </div>
        </div>

        <aside className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex items-start justify-between">
              <div>
                <div className="num text-3xl font-bold text-slate-900">{euro(l.price_eur)}</div>
                {l.first_price_eur && l.first_price_eur !== l.price_eur && <div className="num text-sm text-slate-400 line-through">{euro(l.first_price_eur)}</div>}
                <div className="mt-2"><DealBadge deal={l.deal_score} confidence={l.valuation_confidence} eur={l.deal_eur} /></div>
              </div>
              <ScoreRing value={l.match} size={64} />
            </div>
            <div className="mt-4 grid grid-cols-2 gap-2">
              <Button variant={l.watchlist ? "primary" : "secondary"} onClick={() => watch.mutate()}>
                <Heart className={clsx("h-4 w-4", l.watchlist && "fill-white")} /> {l.watchlist ? "Favoriet" : "Bewaar"}
              </Button>
              <Button variant={inCompare ? "primary" : "secondary"} onClick={() => toggleCompare(l.id)}>
                <GitCompare className="h-4 w-4" /> Vergelijk
              </Button>
              <Link to={`/auto/${l.id}/checklist`} className="col-span-1">
                <Button variant="secondary" className="w-full"><ClipboardCheck className="h-4 w-4" /> Checklist</Button>
              </Link>
              {!l.is_demo && l.url ? (
                <a href={l.url} target="_blank" rel="noreferrer">
                  <Button variant="secondary" className="w-full"><ExternalLink className="h-4 w-4" /> Advertentie</Button>
                </a>
              ) : (
                <Button variant="secondary" disabled title="Demo-advertentie">
                  <ExternalLink className="h-4 w-4" /> Advertentie
                </Button>
              )}
            </div>
            {profileId && (
              <div className="mt-3 flex items-center justify-center gap-2 text-xs text-slate-500">
                Leer mijn voorkeur:
                <button onClick={() => feedback.mutate(l.feedback === 1 ? 0 : 1)} className={clsx("rounded p-1.5", l.feedback === 1 ? "bg-emerald-100 text-emerald-700" : "hover:bg-slate-100")} aria-label="Leuk">
                  <ThumbsUp className="h-4 w-4" />
                </button>
                <button onClick={() => feedback.mutate(l.feedback === -1 ? 0 : -1)} className={clsx("rounded p-1.5", l.feedback === -1 ? "bg-rose-100 text-rose-700" : "hover:bg-slate-100")} aria-label="Niet leuk">
                  <ThumbsDown className="h-4 w-4" />
                </button>
              </div>
            )}
            {l.duplicates.length > 0 && (
              <div className="mt-3 border-t border-slate-100 pt-3 text-xs text-slate-600">
                Ook aangeboden op:{" "}
                {l.duplicates.map((d) => (
                  <a key={d.id} href={d.url} target="_blank" rel="noreferrer" className="mr-2 text-brand-700 hover:underline">
                    {d.source_label} ({euro(d.price_eur)})
                  </a>
                ))}
              </div>
            )}
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="mb-3 text-sm font-semibold text-slate-900">Opbouw match-score</h2>
            <ScoreBreakdown l={l} />
          </div>
        </aside>
      </div>

      {(flags.length > 0 || infos.length > 0) && (
        <Section title="Let op" icon={<AlertTriangle className="h-5 w-5 text-amber-600" />}>
          <div className="space-y-2">
            {flags.map((f) => (
              <div key={f.code} className="flex gap-3 text-sm">
                <Badge tone={severityTone(f.severity)} className="shrink-0">{f.severity === "high" ? "Hoog" : f.severity === "medium" ? "Middel" : "Laag"}</Badge>
                <div><span className="font-medium">{f.title}.</span> <span className="text-slate-600">{f.detail}</span></div>
              </div>
            ))}
            {infos.length > 0 && <div className="flex flex-wrap gap-1.5 pt-1">{infos.map((f) => <Badge key={f.code} tone="info" title={f.detail}>{f.title}</Badge>)}</div>}
          </div>
        </Section>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <Section title="Marktwaarde" icon={<LineIcon className="h-5 w-5 text-brand-700" />}>
          {l.predicted_price && l.predicted_low && l.predicted_high && l.price_eur ? (
            <>
              <ValueBand low={l.predicted_low} mid={l.predicted_price} high={l.predicted_high} price={l.price_eur} />
              <div className="space-y-1.5 text-sm text-slate-700">
                <p>
                  Geschatte marktwaarde <b>{euro(l.predicted_price)}</b> (80% van vergelijkbare auto's tussen {euro(l.predicted_low)} en {euro(l.predicted_high)}). Betrouwbaarheid:{" "}
                  <b>{l.valuation_confidence === "high" ? "hoog" : l.valuation_confidence === "medium" ? "gemiddeld" : "laag"}</b>.
                </p>
                {l.km_effect_eur != null && l.expected_km != null && l.mileage_km != null && Math.abs(l.mileage_km - l.expected_km) > 5000 && (
                  <p>
                    Deze auto heeft {km(Math.abs(l.mileage_km - l.expected_km))} {l.mileage_km > l.expected_km ? "méér" : "minder"} gereden dan gebruikelijk voor zijn leeftijd. De markt
                    rekent daarvoor ongeveer <b>{euro(Math.abs(l.km_effect_eur))}</b> {l.km_effect_eur < 0 ? "minder" : "extra"}; dat zit al in de marktwaarde verwerkt.
                  </p>
                )}
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-500">Nog te weinig vergelijkbare auto's voor een betrouwbare schatting.</p>
          )}
          {l.depreciation.length > 1 && (
            <div className="mt-4">
              <div className="mb-1 text-xs font-medium text-slate-500">Verwachte waarde de komende jaren (13.000 km/jaar)</div>
              <div className="h-40">
                <ResponsiveContainer>
                  <LineChart data={l.depreciation} margin={{ left: 10, right: 10, top: 5, bottom: 0 }}>
                    <CartesianGrid stroke="#f1f5f9" />
                    <XAxis dataKey="year" tickFormatter={(v) => (v === 0 ? "nu" : `+${v}j`)} fontSize={11} />
                    <YAxis tickFormatter={(v) => `€${Math.round(v / 1000)}k`} fontSize={11} width={45} />
                    <Tooltip formatter={(v) => euro(Number(v))} labelFormatter={(v) => (v === 0 ? "Nu" : `Over ${v} jaar`)} />
                    <Line dataKey="value" stroke="#0f766e" strokeWidth={2} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </Section>

        <Section title="Vergelijkbare auto's" icon={<GitCompare className="h-5 w-5 text-brand-700" />}>
          {l.comparables.length === 0 ? (
            <p className="text-sm text-slate-500">Geen vergelijkbare auto's gevonden.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-500">
                    <th className="pb-2 font-medium">Auto</th>
                    <th className="pb-2 text-right font-medium">Jaar</th>
                    <th className="pb-2 text-right font-medium">Km</th>
                    <th className="pb-2 text-right font-medium">Prijs</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-t border-slate-100 bg-brand-50/60 font-medium">
                    <td className="py-1.5">Deze auto</td>
                    <td className="num py-1.5 text-right">{l.year}</td>
                    <td className="num py-1.5 text-right">{km(l.mileage_km)}</td>
                    <td className="num py-1.5 text-right">{euro(l.price_eur)}</td>
                  </tr>
                  {l.comparables.map((c) => (
                    <tr key={c.id} className="border-t border-slate-100">
                      <td className="max-w-[200px] truncate py-1.5">
                        <Link to={`/auto/${c.id}`} className="hover:text-brand-700">{c.trim || c.title}</Link>
                        {c.status !== "active" && <span className="ml-1 text-xs text-slate-400">(verkocht)</span>}
                      </td>
                      <td className="num py-1.5 text-right">{c.year}</td>
                      <td className="num py-1.5 text-right">{km(c.mileage_km)}</td>
                      <td className="num py-1.5 text-right">{euro(c.price_eur)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>
      </div>

      <Section
        title={`Aandachtspunten ${l.model_name ?? ""}`}
        icon={<Wrench className="h-5 w-5 text-amber-600" />}
        actions={l.make && l.model ? <Link to={`/aandachtspunten/${l.make}/${l.model}`} className="text-xs text-brand-700 hover:underline">Alles over dit model</Link> : null}
      >
        {l.model_overview?.summary && <p className="mb-3 text-sm text-slate-700">{l.model_overview.summary}</p>}
        {l.issues.length > 0 ? (
          <div className="space-y-2">
            {l.issues.map((i, idx) => <IssueCard key={i.id} issue={i} defaultOpen={idx === 0} />)}
          </div>
        ) : l.model_overview?.has_model_specific ? (
          <p className="text-sm text-slate-600">Geen bekende problemen die op deze uitvoering/bouwjaar van toepassing zijn.</p>
        ) : l.make && l.model ? (
          <Research make={l.make} model={l.model} />
        ) : null}
      </Section>

      {l.vehicle && (
        <Section title="RDW-rapport" icon={<ShieldCheck className="h-5 w-5 text-brand-700" />}>
          <RdwReport v={l.vehicle} />
        </Section>
      )}
      {!l.vehicle && (
        <Section title="RDW-rapport" icon={<ShieldCheck className="h-5 w-5 text-slate-400" />}>
          <p className="text-sm text-slate-600">
            Geen kenteken in de advertentie gevonden. Vraag het kenteken aan de verkoper en controleer het via <Link to="/kenteken" className="text-brand-700 hover:underline">Kenteken-check</Link>.
          </p>
        </Section>
      )}

      {l.ev && (
        <Section title="Elektrisch rijden" icon={<Battery className="h-5 w-5 text-emerald-600" />}>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2 text-sm">
              <div className="font-medium">Batterijgarantie</div>
              <p className="text-slate-700">
                {l.ev.warranty.years} jaar / {km(l.ev.warranty.km ?? null)}
                {l.ev.warranty.min_soh_pct ? `, minimaal ${l.ev.warranty.min_soh_pct}% capaciteit` : ""}
                {l.ev.warranty_is_default && <span className="text-slate-400"> (gangbare garantie; check merk)</span>}
              </p>
              {l.ev.warranty_years_left != null && (
                <Badge tone={l.ev.warranty_covered ? "good" : "warn"}>
                  {l.ev.warranty_covered ? `Nog ${l.ev.warranty_years_left} jaar / ${km(l.ev.warranty_km_left)} garantie` : "Batterijgarantie verlopen"}
                </Badge>
              )}
              {l.ev.warranty.note && <p className="text-xs text-slate-500">{l.ev.warranty.note}</p>}
              <div className="flex flex-wrap gap-1.5 pt-1">
                <Badge tone={l.ev.heat_pump ? "good" : "ok"}>{l.ev.heat_pump ? "Warmtepomp" : "Warmtepomp niet vermeld"}</Badge>
                {l.ev.battery_lease && <Badge tone="warn">Huuraccu</Badge>}
              </div>
            </div>
            {l.ev.range && (
              <div className="grid grid-cols-2 gap-2">
                <Stat label="WLTP" value={`${l.ev.range.wltp} km`} />
                <Stat label="Zomer (praktijk)" value={`${l.ev.range.zomer} km`} />
                <Stat label="Winter (praktijk)" value={`${l.ev.range.winter} km`} />
                <Stat label="Snelweg 130 km/u" value={`${l.ev.range.snelweg_130} km`} />
              </div>
            )}
          </div>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-600">{l.ev.advice.map((a) => <li key={a}>{a}</li>)}</ul>
        </Section>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <Section title="Wat kost deze auto per maand?" icon={<Wallet className="h-5 w-5 text-brand-700" />}>
          <TcoPanel listingId={l.id} />
        </Section>
        {l.negotiation && (
          <Section title="Onderhandelen" icon={<Handshake className="h-5 w-5 text-brand-700" />}>
            <div className="grid grid-cols-3 gap-2">
              <Stat label="Openingsbod" value={euro(l.negotiation.opening_bid)} />
              <Stat label="Maximaal" value={euro(l.negotiation.walk_away)} />
              <Stat label="Vraagprijs" value={euro(l.negotiation.asking)} />
            </div>
            <div className="mt-3 text-xs font-semibold uppercase text-slate-500">Argumenten</div>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700">{l.negotiation.arguments.map((a) => <li key={a}>{a}</li>)}</ul>
            <div className="mt-3 text-xs font-semibold uppercase text-slate-500">Tips</div>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-600">{l.negotiation.tips.map((a) => <li key={a}>{a}</li>)}</ul>
          </Section>
        )}
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        {l.price_history.length > 1 && (
          <Section title="Prijsverloop">
            <div className="h-44">
              <ResponsiveContainer>
                <LineChart data={l.price_history.map((p) => ({ ...p, d: date(p.date) }))} margin={{ left: 10, right: 10 }}>
                  <CartesianGrid stroke="#f1f5f9" />
                  <XAxis dataKey="d" fontSize={11} />
                  <YAxis tickFormatter={(v) => euro(Number(v))} fontSize={11} width={70} domain={[(min: number) => Math.floor((min * 0.97) / 100) * 100, (max: number) => Math.ceil((max * 1.02) / 100) * 100]} />
                  <Tooltip formatter={(v) => euro(Number(v))} />
                  <Line type="stepAfter" dataKey="price" stroke="#0f766e" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Section>
        )}
        <Section title="AI-check van de advertentie" icon={<Bot className="h-5 w-5 text-violet-600" />}>
          <AdScan id={l.id} />
        </Section>
      </div>

      {l.description && (
        <Section title="Omschrijving">
          <p className={clsx("whitespace-pre-line text-sm text-slate-700", !showDesc && "line-clamp-6")}>{l.description}</p>
          {l.description.length > 400 && (
            <button className="mt-2 text-sm text-brand-700 hover:underline" onClick={() => setShowDesc((s) => !s)}>
              {showDesc ? "Minder" : "Meer lezen"}
            </button>
          )}
        </Section>
      )}
    </div>
  );
}
