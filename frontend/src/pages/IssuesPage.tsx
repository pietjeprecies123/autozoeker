import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, FileSearch, Wrench } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import IssueCard from "../components/IssueCard";
import { Badge, Button, Card, ErrorBox, Section, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { date, severityOrder } from "../lib/format";
import { useApp } from "../lib/store";

function ModelIssues({ make, model }: { make: string; model: string }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["issues", make, model], queryFn: () => api.issuesForModel(make, model) });
  const research = useMutation({
    mutationFn: (force: boolean) => api.research(make, model, force),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["issues"] }),
  });
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBox error={q.error} />;
  const d = q.data;
  const o = d.overview;
  const issues = [...(o?.issues ?? [])].sort((a, b) => (severityOrder[a.severity] ?? 9) - (severityOrder[b.severity] ?? 9));
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold">{d.title}: bekende aandachtspunten</h1>
        <Link to={`/?f=${btoa(JSON.stringify({ models: [`${make}/${model}`] }))}`} className="text-sm text-brand-700 hover:underline">Zoek deze auto →</Link>
      </div>
      {o?.source === "ai" && (
        <div className="rounded-lg border border-violet-200 bg-violet-50 p-3 text-sm text-violet-900">
          AI-onderzocht met Claude + webzoekopdrachten{d.ai_research && ` op ${date(d.ai_research.created_at)} (≈ $${d.ai_research.cost_usd.toFixed(2)})`}. Controleer de bronnen; de samengestelde kennisbank gaat voor.
        </div>
      )}
      {o && o.files.length > 1 ? (
        <div className="grid gap-3 md:grid-cols-2">
          {o.files.map((f) => (
            <Card key={f.id} className="space-y-1 p-4 text-sm">
              <div className="font-semibold">{f.title}</div>
              <p className="text-slate-700">{f.summary}</p>
            </Card>
          ))}
        </div>
      ) : (
        o?.summary && <p className="text-slate-700">{o.summary}</p>
      )}
      {o?.battery_warranty && (
        <Card className="p-4 text-sm">
          <b>Batterijgarantie{o.files.length > 1 ? " (elektrische uitvoering)" : ""}:</b> {o.battery_warranty.years} jaar / {o.battery_warranty.km?.toLocaleString("nl-NL")} km
          {o.battery_warranty.min_soh_pct ? `, minimaal ${o.battery_warranty.min_soh_pct}%` : ""}. {o.battery_warranty.note}
        </Card>
      )}
      {issues.length > 0 ? (
        <div className="space-y-2">{issues.map((i, idx) => <IssueCard key={`${i.file_id}-${i.id}`} issue={i} defaultOpen={idx < 2} />)}</div>
      ) : (
        <Card className="space-y-3 p-5 text-sm">
          <p className="text-slate-600">Voor dit model staat nog niets in de kennisbank.</p>
          {d.ai_available ? (
            <Button onClick={() => research.mutate(false)} disabled={research.isPending}>
              <FileSearch className="h-4 w-4" /> {research.isPending ? "Claude zoekt bronnen (±1 min)…" : "Onderzoek met AI (geschat €0,30–0,80)"}
            </Button>
          ) : (
            <p className="text-slate-500">Stel <code>ANTHROPIC_API_KEY</code> in om dit automatisch te laten onderzoeken.</p>
          )}
          {research.error && <ErrorBox error={research.error} />}
        </Card>
      )}
      {o && o.general_checks.length > 0 && (
        <Section title="Algemene controlepunten voor dit model">
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">{o.general_checks.map((c) => <li key={c}>{c}</li>)}</ul>
        </Section>
      )}
      {o?.source === "ai" && d.ai_available && (
        <Button variant="ghost" size="sm" onClick={() => research.mutate(true)} disabled={research.isPending}>Opnieuw onderzoeken</Button>
      )}
    </div>
  );
}

export default function IssuesPage() {
  const { make, model } = useParams();
  const navigate = useNavigate();
  const { meta } = useApp();
  const idx = useQuery({ queryKey: ["issues-index"], queryFn: api.issues, enabled: !make });
  if (make && model) return <ModelIssues make={make} model={model} />;
  if (!meta) return <Spinner />;
  const covered = new Set<string>();
  idx.data?.curated.forEach((f) => f.applies_to.forEach((t) => t.model && covered.add(`${t.make}/${t.model}`)));
  return (
    <div className="space-y-5">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-bold"><Wrench className="h-5 w-5 text-amber-600" />Aandachtspunten per model</h1>
        <p className="text-sm text-slate-600">
          Bekende, modelspecifieke problemen met bronnen, de vragen die je de verkoper stelt om te checken of het al is opgelost, en waar je op let tijdens de proefrit.
          Waar het om een terugroepactie gaat, controleert Autozoeker per kenteken bij de RDW of die al is uitgevoerd.
        </p>
      </div>
      <Card className="p-4">
        <select
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          onChange={(e) => e.target.value && navigate(`/aandachtspunten/${e.target.value}`)}
          defaultValue=""
          aria-label="Kies model"
        >
          <option value="">Kies een model…</option>
          {meta.catalog.map((mk) => (
            <optgroup key={mk.slug} label={mk.name}>
              {mk.models.map((md) => (
                <option key={md.slug} value={`${mk.slug}/${md.slug}`}>
                  {mk.name} {md.name} {covered.has(`${mk.slug}/${md.slug}`) ? "✓" : ""}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </Card>
      <Section title="In de kennisbank" icon={<BookOpen className="h-5 w-5 text-brand-700" />}>
        {idx.isLoading && <Spinner />}
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {idx.data?.curated.map((f) => {
            const t = f.applies_to.find((a) => a.model) ?? f.applies_to[0];
            return (
              <Link key={f.id} to={t?.model ? `/aandachtspunten/${t.make}/${t.model}` : "#"} className="rounded-lg border border-slate-200 bg-white p-3 hover:border-brand-400">
                <div className="font-medium text-slate-900">{f.title}</div>
                <div className="text-xs text-slate-500">{f.n_issues} aandachtspunten · bijgewerkt {f.reviewed}</div>
              </Link>
            );
          })}
          {idx.data?.ai.map((r) => (
            <Link key={r.key} to={`/aandachtspunten/${r.make}/${r.model}`} className="rounded-lg border border-violet-200 bg-violet-50/40 p-3 hover:border-violet-400">
              <div className="flex items-center gap-2 font-medium text-slate-900">{r.title} <Badge tone="demo">AI</Badge></div>
              <div className="text-xs text-slate-500">onderzocht {date(r.created_at)}</div>
            </Link>
          ))}
        </div>
      </Section>
    </div>
  );
}
