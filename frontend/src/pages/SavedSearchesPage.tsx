import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, BellOff, Search, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge, Button, Card, Empty, ErrorBox, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { date, euro } from "../lib/format";
import { useApp } from "../lib/store";
import type { SavedSearch } from "../lib/types";
import { filterSummary } from "./SearchPage";

function toUrl(s: SavedSearch) {
  const enc = (v: unknown) => btoa(unescape(encodeURIComponent(JSON.stringify(v))));
  const p = new URLSearchParams();
  if (Object.keys(s.filters || {}).length) p.set("f", enc(s.filters));
  if (Object.keys(s.weights || {}).length) p.set("w", enc(s.weights));
  return `/?${p.toString()}`;
}

export default function SavedSearchesPage() {
  const { profileId, meta } = useApp();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["saved", profileId], queryFn: () => api.savedSearches(profileId!), enabled: !!profileId });
  const update = useMutation({
    mutationFn: ({ s, patch }: { s: SavedSearch; patch: Partial<SavedSearch> }) =>
      api.updateSavedSearch(s.id, { ...s, ...patch, top: undefined, current_matches: undefined, total_results: undefined } as Partial<SavedSearch>),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["saved"] }),
  });
  const remove = useMutation({ mutationFn: (id: number) => api.deleteSavedSearch(id), onSuccess: () => qc.invalidateQueries({ queryKey: ["saved"] }) });

  if (!profileId) return <Spinner label="Kies eerst een profiel" />;
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorBox error={q.error} />;
  const items = q.data ?? [];
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold">Zoekopdrachten</h1>
        <p className="text-sm text-slate-600">
          Bij elke crawl-ronde worden nieuwe auto's, prijsdalingen en auto's die weer online komen vergeleken met deze zoekopdrachten.
          {!meta?.ntfy_configured && " Stel bij Status een ntfy-topic in om pushmeldingen op je telefoon te krijgen."}
        </p>
      </div>
      {items.length === 0 && (
        <Empty title="Nog geen zoekopdrachten" icon={<Search className="h-8 w-8 text-slate-400" />}>
          Stel bij <Link to="/" className="text-brand-700 hover:underline">Zoeken</Link> je filters in en klik op "Bewaar &amp; volg".
        </Empty>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        {items.map((s) => (
          <Card key={s.id} className="flex flex-col gap-3 p-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <Link to={toUrl(s)} className="font-semibold text-slate-900 hover:text-brand-700">{s.name}</Link>
                <div className="text-xs text-slate-500">{filterSummary(s.filters)}</div>
              </div>
              <Badge tone={s.alert_mode === "off" ? "none" : "brand"}>
                {s.alert_mode === "instant" ? "Direct" : s.alert_mode === "daily" ? "Dagelijks" : "Geen meldingen"}
              </Badge>
            </div>
            <div className="num flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-600">
              <span><b className="text-slate-900">{s.total_results ?? "–"}</b> resultaten</span>
              <span><b className="text-slate-900">{s.current_matches ?? "–"}</b> met match ≥ {s.min_match}</span>
              <span>{s.alerts_total} meldingen</span>
            </div>
            {s.top && s.top.length > 0 && (
              <ul className="space-y-1 text-sm">
                {s.top.map((l) => (
                  <li key={l.id} className="flex justify-between gap-2">
                    <Link to={`/auto/${l.id}`} className="truncate hover:text-brand-700">{l.title}</Link>
                    <span className="num shrink-0 text-slate-600">{euro(l.price_eur)} · {l.match}</span>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-auto flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3 text-sm">
              <label className="flex items-center gap-1.5 text-xs text-slate-600">
                Min. match
                <input
                  type="number"
                  className="w-16 rounded border border-slate-300 px-1.5 py-0.5"
                  defaultValue={s.min_match}
                  onBlur={(e) => Number(e.target.value) !== s.min_match && update.mutate({ s, patch: { min_match: Number(e.target.value) } })}
                />
              </label>
              <select
                value={s.alert_mode}
                onChange={(e) => update.mutate({ s, patch: { alert_mode: e.target.value as SavedSearch["alert_mode"] } })}
                className="rounded border border-slate-300 px-1.5 py-0.5 text-xs"
                aria-label="Meldingen"
              >
                <option value="instant">Direct</option>
                <option value="daily">Dagelijks</option>
                <option value="off">Uit</option>
              </select>
              <span className="text-xs text-slate-400">sinds {date(s.created_at)}</span>
              <div className="ml-auto flex gap-1">
                <Button size="sm" variant="ghost" onClick={() => update.mutate({ s, patch: { alert_mode: s.alert_mode === "off" ? "instant" : "off" } })} title="Meldingen aan/uit">
                  {s.alert_mode === "off" ? <Bell className="h-4 w-4" /> : <BellOff className="h-4 w-4" />}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => remove.mutate(s.id)} title="Verwijderen">
                  <Trash2 className="h-4 w-4 text-rose-600" />
                </Button>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
