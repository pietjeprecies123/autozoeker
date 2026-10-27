import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, BellRing, Database, Play, RefreshCw, Save, UserCog } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge, Button, ErrorBox, Section, Spinner, Stat } from "../components/ui";
import { api } from "../lib/api";
import { date } from "../lib/format";
import { useApp } from "../lib/store";

function ProfileSettings() {
  const { profileId } = useApp();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["profiles"], queryFn: api.profiles });
  const p = q.data?.find((x) => x.id === profileId);
  const [postcode, setPostcode] = useState("");
  const [topic, setTopic] = useState("");
  useEffect(() => {
    setPostcode(p?.home_postcode ?? "");
    setTopic(p?.ntfy_topic ?? "");
  }, [p?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const save = useMutation({
    mutationFn: () => api.updateProfile(profileId!, { home_postcode: postcode || null, ntfy_topic: topic || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profiles"] });
      qc.invalidateQueries({ queryKey: ["meta"] });
    },
  });
  const push = useMutation({ mutationFn: () => api.testPush(profileId!) });
  const suggest = () => setTopic(`autozoeker-${p?.name.toLowerCase() ?? "ik"}-${Math.random().toString(36).slice(2, 10)}`);
  if (!p) return null;
  return (
    <Section title={`Profiel ${p.name}`} icon={<UserCog className="h-5 w-5 text-brand-700" />}>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="text-slate-600">Postcode thuis (voor afstand)</span>
          <input className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" value={postcode} onChange={(e) => setPostcode(e.target.value)} placeholder="3511" />
        </label>
        <label className="block text-sm">
          <span className="text-slate-600">ntfy-topic voor pushmeldingen</span>
          <div className="mt-1 flex gap-2">
            <input className="w-full rounded-lg border border-slate-300 px-3 py-2" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="autozoeker-pim-x7k2…" />
            <Button variant="secondary" onClick={suggest} type="button">Genereer</Button>
          </div>
        </label>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Installeer de gratis ntfy-app (iOS/Android), abonneer op hetzelfde topic en je krijgt meldingen. Het topic werkt als wachtwoord: kies iets onraadbaars, of draai je eigen
        ntfy-server en zet <code>NTFY_SERVER</code>/<code>NTFY_TOKEN</code>.
      </p>
      {p.learned_weights && Object.keys(p.learned_weights).length > 0 && (
        <p className="mt-2 text-xs text-slate-500">
          Geleerde voorkeur uit je duimpjes: {Object.entries(p.learned_weights).map(([k, v]) => `${k} ${Math.round(v * 100)}%`).join(" · ")}
        </p>
      )}
      <div className="mt-4 flex gap-2">
        <Button onClick={() => save.mutate()} disabled={save.isPending}><Save className="h-4 w-4" />Opslaan</Button>
        <Button variant="secondary" onClick={() => push.mutate()} disabled={push.isPending}><BellRing className="h-4 w-4" />Testmelding</Button>
      </div>
      {save.isSuccess && <p className="mt-2 text-sm text-emerald-700">Opgeslagen.</p>}
      {push.isSuccess && <p className="mt-2 text-sm text-emerald-700">Testmelding verstuurd.</p>}
      {push.error && <div className="mt-2"><ErrorBox error={push.error} /></div>}
    </Section>
  );
}

export default function StatusPage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["status"], queryFn: api.status, refetchInterval: 15_000 });
  const crawl = useMutation({ mutationFn: api.crawlNow, onSuccess: () => setTimeout(() => qc.invalidateQueries(), 3000) });
  const retrain = useMutation({ mutationFn: api.retrain, onSuccess: () => setTimeout(() => qc.invalidateQueries({ queryKey: ["status"] }), 5000) });
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBox error={q.error} />;
  const s = q.data;
  return (
    <div className="space-y-5">
      <h1 className="flex items-center gap-2 text-xl font-bold"><Activity className="h-5 w-5 text-brand-700" />Status &amp; instellingen</h1>
      <ProfileSettings />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-8">
        <Stat label="Actieve advertenties" value={s.listings.active ?? 0} />
        <Stat label="Offline/verkocht" value={s.listings.removed ?? 0} />
        <Stat label="RDW-records" value={s.vehicles} />
        <Stat label="Zoekopdrachten" value={s.saved_searches} />
        <Stat label="Favorieten" value={s.watchlist} />
        <Stat label="Meldingen" value={s.alerts} />
        <Stat label="Waarderingsfout (mediaan)" value={s.valuation.metrics?.median_ape_pct != null ? `${s.valuation.metrics.median_ape_pct}%` : "–"} sub={`${s.valuation.rows} auto's`} />
        <Stat label="Binnen 10%" value={s.valuation.metrics?.within_10pct != null ? `${s.valuation.metrics.within_10pct}%` : "–"} sub={s.valuation.trained_at ? date(s.valuation.trained_at) : "niet getraind"} />
      </div>
      <Section
        title="Bronnen"
        icon={<Database className="h-5 w-5 text-brand-700" />}
        actions={
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" onClick={() => retrain.mutate()} disabled={retrain.isPending}><RefreshCw className="h-4 w-4" />Hertrain model</Button>
            <Button size="sm" onClick={() => crawl.mutate()} disabled={crawl.isPending}><Play className="h-4 w-4" />Nu crawlen</Button>
          </div>
        }
      >
        <div className="grid gap-2 sm:grid-cols-3">
          {s.sources.map((src: any) => (
            <div key={src.name} className="rounded-lg border border-slate-200 p-3 text-sm">
              <div className="flex items-center justify-between font-medium">
                {src.label}
                <Badge tone={src.enabled ? "good" : "none"}>{src.enabled ? "aan" : "uit"}</Badge>
              </div>
              <div className="mt-1 text-xs text-slate-500">
                {src.verified ? "Parser geverifieerd" : "Parser niet geverifieerd – draai `autozoeker verify-sources`"} · actief: {s.active_by_source[src.name] ?? 0}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-3 text-xs text-slate-500">
          Crawl elke {s.settings.crawl_interval_min} min · {s.settings.request_delay_s}s tussen verzoeken · AI {s.settings.ai_enabled ? `aan (${s.settings.claude_model})` : "uit"} · ntfy{" "}
          {s.settings.ntfy_server} · RDW/PDOK online: {s.settings.online_enrichment ? "ja" : "nee"}
        </div>
        {s.scheduler?.jobs?.length > 0 && (
          <div className="mt-2 text-xs text-slate-500">
            Volgende runs: {s.scheduler.jobs.map((j: any) => `${j.id} ${date(j.next_run)} ${j.next_run ? new Date(j.next_run).toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit" }) : ""}`).join(" · ")}
          </div>
        )}
      </Section>
      <Section title="Laatste crawl-runs">
        {s.crawl_runs.length === 0 ? (
          <p className="text-sm text-slate-500">Nog geen runs van echte bronnen. In demo-modus worden elke ronde nieuwe demo-auto's en prijswijzigingen gesimuleerd.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500">
                  <th className="pb-2">Bron</th>
                  <th className="pb-2">Zoekvraag</th>
                  <th className="pb-2">Start</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2 text-right">Opgehaald</th>
                  <th className="pb-2 text-right">Nieuw</th>
                  <th className="pb-2 text-right">Fouten</th>
                </tr>
              </thead>
              <tbody>
                {s.crawl_runs.map((r: any) => (
                  <tr key={r.id} className="border-t border-slate-100" title={r.error}>
                    <td className="py-1.5">{r.source}</td>
                    <td className="max-w-[240px] truncate py-1.5 text-slate-500">{r.query}</td>
                    <td className="py-1.5">{date(r.started_at)}</td>
                    <td className="py-1.5">
                      <Badge tone={r.status === "ok" ? "good" : r.status === "blocked" || r.status === "error" ? "bad" : "warn"}>{r.status}</Badge>
                    </td>
                    <td className="num py-1.5 text-right">{r.fetched}</td>
                    <td className="num py-1.5 text-right">{r.new}</td>
                    <td className="num py-1.5 text-right">{r.errors}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </div>
  );
}
