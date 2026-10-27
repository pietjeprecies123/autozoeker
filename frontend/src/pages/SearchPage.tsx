import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { BellPlus, Download, LineChart, List, Map as MapIcon, SlidersHorizontal, Sparkles, Wand2 } from "lucide-react";
import { Suspense, lazy, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ListingRow } from "../components/car";
import Filters from "../components/Filters";
import { Badge, Button, Card, Empty, ErrorBox, Modal, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { euro, km, pct } from "../lib/format";
import { useApp } from "../lib/store";
import type { SearchFilters, Weights } from "../lib/types";

const ResultMap = lazy(() => import("../components/ResultMap"));
const ParetoChart = lazy(() => import("../components/ParetoChart"));

const SORTS: Record<string, string> = {
  best: "Beste match",
  deal: "Grootste voordeel",
  price_asc: "Prijs laag–hoog",
  price_desc: "Prijs hoog–laag",
  km: "Minste kilometers",
  year: "Nieuwste bouwjaar",
  newest: "Nieuw binnen",
  distance: "Dichtstbij",
};

function decode<T>(s: string | null, fallback: T): T {
  if (!s) return fallback;
  try {
    return JSON.parse(decodeURIComponent(escape(atob(s)))) as T;
  } catch {
    return fallback;
  }
}
function encode(v: unknown): string {
  return btoa(unescape(encodeURIComponent(JSON.stringify(v))));
}
function clean(f: SearchFilters): SearchFilters {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(f)) {
    if (v === null || v === undefined || v === "" || v === false) continue;
    if (Array.isArray(v) && v.length === 0) continue;
    out[k] = v;
  }
  return out as SearchFilters;
}

export function filterSummary(f: SearchFilters): string {
  const parts: string[] = [];
  if (f.models?.length) parts.push(f.models.map((m) => m.split("/")[1]).join(", "));
  if (f.makes?.length) parts.push(f.makes.join(", "));
  if (f.fuels?.length) parts.push(f.fuels.join("/"));
  if (f.bodies?.length) parts.push(f.bodies.join("/"));
  if (f.price_max) parts.push(`tot ${euro(f.price_max)}`);
  if (f.km_max) parts.push(`max ${km(f.km_max)}`);
  if (f.year_min) parts.push(`vanaf ${f.year_min}`);
  if (f.transmissions?.length) parts.push(f.transmissions.join("/"));
  return parts.join(" · ") || "Alle auto's";
}

function WeightsModal({ open, onClose, weights, setWeights }: { open: boolean; onClose: () => void; weights: Weights; setWeights: (w: Weights) => void }) {
  const { meta } = useApp();
  if (!meta) return null;
  const merged = { ...meta.weights, ...weights };
  const total = Object.values(merged).reduce((a, b) => a + b, 0) || 1;
  return (
    <Modal open={open} onClose={onClose} title="Wat vind jij belangrijk?">
      <p className="mb-4 text-sm text-slate-600">
        De match-score (0–100) combineert deze onderdelen. Schuif om het gewicht aan te passen; ze worden automatisch naar 100% geschaald.
      </p>
      <div className="space-y-4">
        {Object.entries(meta.weight_labels).map(([k, label]) => (
          <div key={k}>
            <div className="mb-1 flex justify-between text-sm">
              <span>{label}</span>
              <span className="num text-slate-500">{Math.round(((merged[k] ?? 0) / total) * 100)}%</span>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={merged[k] ?? 0}
              onChange={(e) => setWeights({ ...merged, [k]: Number(e.target.value) })}
              className="w-full"
              aria-label={label}
            />
          </div>
        ))}
      </div>
      <div className="mt-5 flex justify-between">
        <Button variant="ghost" onClick={() => setWeights({})}>Standaard</Button>
        <Button onClick={onClose}>Klaar</Button>
      </div>
    </Modal>
  );
}

function SaveSearchModal({ open, onClose, filters, weights }: { open: boolean; onClose: () => void; filters: SearchFilters; weights: Weights }) {
  const { profileId, meta } = useApp();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [mode, setMode] = useState<"instant" | "daily" | "off">("instant");
  const [minMatch, setMinMatch] = useState(60);
  const [dropEur, setDropEur] = useState(250);
  const save = useMutation({
    mutationFn: () =>
      api.createSavedSearch({ profile_id: profileId!, name: name || filterSummary(filters), filters, weights, alert_mode: mode, min_match: minMatch, price_drop_eur: dropEur }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["saved"] });
      onClose();
    },
  });
  return (
    <Modal open={open} onClose={onClose} title="Zoekopdracht bewaren">
      <div className="space-y-4 text-sm">
        <label className="block">
          <span className="text-slate-600">Naam</span>
          <input className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" placeholder={filterSummary(filters)} value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <div>
          <span className="text-slate-600">Meldingen</span>
          <div className="mt-1 grid grid-cols-3 gap-2">
            {(["instant", "daily", "off"] as const).map((m) => (
              <button key={m} onClick={() => setMode(m)} className={clsx("rounded-lg border px-3 py-2", mode === m ? "border-brand-600 bg-brand-50 text-brand-800" : "border-slate-200")}>
                {m === "instant" ? "Direct (push)" : m === "daily" ? "Dagelijks overzicht" : "Uit"}
              </button>
            ))}
          </div>
          {!meta?.ntfy_configured && mode !== "off" && (
            <p className="mt-1 text-xs text-amber-700">Nog geen ntfy-topic ingesteld: meldingen verschijnen dan alleen in de app (Voor jou). Stel een topic in bij Status.</p>
          )}
        </div>
        <label className="block">
          <span className="text-slate-600">Alleen melden vanaf match-score: <b>{minMatch}</b></span>
          <input type="range" min={0} max={95} step={5} value={minMatch} onChange={(e) => setMinMatch(Number(e.target.value))} className="w-full" />
        </label>
        <label className="block">
          <span className="text-slate-600">Prijsdaling melden vanaf (€)</span>
          <input type="number" className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" value={dropEur} onChange={(e) => setDropEur(Number(e.target.value))} />
        </label>
        {save.error && <ErrorBox error={save.error} />}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Annuleren</Button>
          <Button onClick={() => save.mutate()} disabled={!profileId || save.isPending}>
            <BellPlus className="h-4 w-4" /> Bewaren
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export default function SearchPage() {
  const { meta, profileId } = useApp();
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const filters = useMemo(() => decode<SearchFilters>(params.get("f"), {}), [params]);
  const weights = useMemo(() => decode<Weights>(params.get("w"), {}), [params]);
  const sort = params.get("sort") || "best";
  const view = params.get("view") || "list";
  const [pageSize, setPageSize] = useState(30);
  const [nlText, setNlText] = useState("");
  const [nlInfo, setNlInfo] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [weightsOpen, setWeightsOpen] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);

  const update = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v == null || v === "") next.delete(k);
      else next.set(k, v);
    }
    setParams(next, { replace: true });
  };
  const setFilters = (patch: Partial<SearchFilters>) => {
    const f = clean({ ...filters, ...patch });
    update({ f: Object.keys(f).length ? encode(f) : null });
    setPageSize(30);
  };
  const setWeights = (w: Weights) => update({ w: Object.keys(w).length ? encode(w) : null });

  const req = { filters, sort, weights, page: 1, page_size: view === "list" ? pageSize : 400, profile_id: profileId };
  const q = useQuery({ queryKey: ["search", req], queryFn: () => api.search(req), placeholderData: keepPreviousData, enabled: !!meta });

  const parse = useMutation({
    mutationFn: (text: string) => api.parseSearch(text),
    onSuccess: (res) => {
      update({ f: encode(clean(res.filters)), sort: res.sort !== "best" ? res.sort : null });
      setNlInfo(`${res.engine === "claude" ? "Claude" : "Regels"}: ${res.explanation || "filters toegepast"}`);
    },
  });
  const watch = useMutation({
    mutationFn: (id: number) => api.addWatch(id, profileId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["search"] });
      qc.invalidateQueries({ queryKey: ["watchlist"] });
    },
  });

  if (!meta) return <Spinner />;
  const data = q.data;

  return (
    <div className="space-y-5">
      <Card className="p-4">
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            if (nlText.trim()) parse.mutate(nlText.trim());
          }}
        >
          <div className="relative flex-1">
            <Wand2 className="pointer-events-none absolute left-3 top-2.5 h-5 w-5 text-brand-600" />
            <input
              value={nlText}
              onChange={(e) => setNlText(e.target.value)}
              placeholder='Beschrijf je auto, bijv. "zuinige gezinsauto onder 15k met trekhaak, automaat"'
              className="w-full rounded-lg border border-slate-300 py-2 pl-10 pr-3 text-sm focus:border-brand-500 focus:outline-none"
              aria-label="Zoek in gewone taal"
            />
          </div>
          <Button type="submit" disabled={parse.isPending}>
            <Sparkles className="h-4 w-4" /> {parse.isPending ? "Bezig…" : "Zoek"}
          </Button>
        </form>
        {nlInfo && <p className="mt-2 text-xs text-slate-600">{nlInfo}</p>}
        {parse.error && <div className="mt-2"><ErrorBox error={parse.error} /></div>}
      </Card>

      <div className="flex gap-6">
        <aside className={clsx("w-72 shrink-0", showFilters ? "fixed inset-0 z-40 block w-full overflow-y-auto bg-white p-4 lg:static lg:w-72 lg:bg-transparent lg:p-0" : "hidden lg:block")}>
          <Card className="p-4 lg:sticky lg:top-24">
            <Filters meta={meta} filters={filters} set={setFilters} reset={() => update({ f: null })} />
            <Button className="mt-3 w-full lg:hidden" onClick={() => setShowFilters(false)}>Toon {data?.total ?? ""} resultaten</Button>
          </Card>
        </aside>

        <section className="min-w-0 flex-1 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" className="lg:hidden" onClick={() => setShowFilters(true)}>
              <SlidersHorizontal className="h-4 w-4" /> Filters
            </Button>
            <div className="mr-auto">
              <div className="text-sm font-semibold text-slate-900">
                {data ? `${data.total.toLocaleString("nl-NL")} auto's` : "…"} <span className="font-normal text-slate-500">· {filterSummary(filters)}</span>
              </div>
              {data?.stats.count ? (
                <div className="num text-xs text-slate-500">
                  mediaan {euro(data.stats.median_price)} · {km(data.stats.median_km)} · {pct(data.stats.share_under_market)} onder marktwaarde
                </div>
              ) : null}
            </div>
            <select value={sort} onChange={(e) => update({ sort: e.target.value === "best" ? null : e.target.value })} className="rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-sm" aria-label="Sorteren">
              {Object.entries(SORTS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <div className="flex rounded-lg border border-slate-300 bg-white p-0.5" role="group" aria-label="Weergave">
              {[
                { k: "list", icon: List, label: "Lijst" },
                { k: "map", icon: MapIcon, label: "Kaart" },
                { k: "chart", icon: LineChart, label: "Prijs × km" },
              ].map((v) => (
                <button
                  key={v.k}
                  onClick={() => update({ view: v.k === "list" ? null : v.k })}
                  className={clsx("flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs", view === v.k ? "bg-brand-700 text-white" : "text-slate-600")}
                  title={v.label}
                >
                  <v.icon className="h-4 w-4" />
                  <span className="hidden sm:inline">{v.label}</span>
                </button>
              ))}
            </div>
            <Button variant="secondary" onClick={() => setWeightsOpen(true)} title="Gewichten match-score">
              <SlidersHorizontal className="h-4 w-4" />
              <span className="hidden sm:inline">Wat telt</span>
              {Object.keys(weights).length > 0 && <Badge tone="brand">aangepast</Badge>}
            </Button>
            <Button variant="secondary" onClick={() => api.exportCsv({ ...req, page_size: 10000 })} title="Exporteer als CSV (Excel/Power BI)">
              <Download className="h-4 w-4" />
            </Button>
            <Button onClick={() => setSaveOpen(true)} disabled={!profileId}>
              <BellPlus className="h-4 w-4" /> <span className="hidden sm:inline">Bewaar &amp; volg</span>
            </Button>
          </div>

          {q.error && <ErrorBox error={q.error} />}
          {!data && q.isLoading && <Spinner />}
          {data && data.total === 0 && (
            <Empty title="Geen auto's gevonden">Probeer minder filters of een ruimere prijs/kilometerstand. Je kunt de zoekopdracht ook bewaren: dan krijg je een melding zodra er iets binnenkomt.</Empty>
          )}
          {data && data.total > 0 && view === "list" && (
            <div className={clsx("space-y-3", q.isFetching && "opacity-70")}>
              {data.items.map((l) => (
                <ListingRow key={l.id} l={l} onWatch={(id) => watch.mutate(id)} />
              ))}
              {data.items.length < data.total && (
                <div className="flex justify-center pt-2">
                  <Button variant="secondary" onClick={() => setPageSize((n) => n + 30)} disabled={q.isFetching}>
                    Meer laden ({data.total - data.items.length} over)
                  </Button>
                </div>
              )}
            </div>
          )}
          {data && data.total > 0 && view === "map" && (
            <Suspense fallback={<Spinner />}>
              <ResultMap items={data.items} />
              <p className="text-xs text-slate-500">Kleur = prijs t.o.v. markt (groen = voordelig), grootte = match-score. Toont de beste {data.items.length} resultaten.</p>
            </Suspense>
          )}
          {data && data.total > 0 && view === "chart" && (
            <Suspense fallback={<Spinner />}>
              <ParetoChart points={data.pareto} />
            </Suspense>
          )}
        </section>
      </div>
      <WeightsModal open={weightsOpen} onClose={() => setWeightsOpen(false)} weights={weights} setWeights={setWeights} />
      <SaveSearchModal open={saveOpen} onClose={() => setSaveOpen(false)} filters={filters} weights={weights} />
    </div>
  );
}
