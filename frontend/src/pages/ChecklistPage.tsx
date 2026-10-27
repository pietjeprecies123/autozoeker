import { useMutation, useQuery } from "@tanstack/react-query";
import { Printer } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Badge, Button, ErrorBox, Spinner, severityTone } from "../components/ui";
import { api } from "../lib/api";
import { euro, km } from "../lib/format";
import { readLocal, writeLocal } from "../lib/store";

export default function ChecklistPage() {
  const { id } = useParams();
  const listingId = Number(id);
  const q = useQuery({ queryKey: ["checklist", listingId], queryFn: () => api.checklist(listingId) });
  const watchQ = useQuery({ queryKey: ["watchlist"], queryFn: api.watchlist });
  const watch = watchQ.data?.items.find((w) => w.id === listingId)?.watch;
  const storageKey = `az.checklist.${listingId}`;
  const [checked, setChecked] = useState<Record<string, boolean>>(() => readLocal(storageKey, {}));
  useEffect(() => {
    if (watch?.checklist_state && Object.keys(watch.checklist_state).length) setChecked(watch.checklist_state);
  }, [watch?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const save = useMutation({ mutationFn: (state: Record<string, boolean>) => api.updateWatch(watch!.id, { checklist_state: state }) });

  const toggle = (key: string) => {
    const next = { ...checked, [key]: !checked[key] };
    setChecked(next);
    writeLocal(storageKey, next);
    if (watch) save.mutate(next);
  };

  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBox error={q.error ?? "Niet gevonden"} />;
  const { listing: l, sections, model_issues } = q.data;
  const all = sections.flatMap((s) => s.items.map((i) => `${s.title}|${i}`)).concat(
    model_issues.flatMap((m) => [...m.questions, ...m.verify, ...m.test_drive].map((i) => `${m.title}|${i}`)),
  );
  const done = all.filter((k) => checked[k]).length;

  const Item = ({ k, text }: { k: string; text: string }) => (
    <label className="flex cursor-pointer gap-2.5 py-1 text-sm">
      <input type="checkbox" className="mt-0.5 h-4 w-4 shrink-0 accent-brand-700" checked={!!checked[k]} onChange={() => toggle(k)} />
      <span className={checked[k] ? "text-slate-400 line-through" : "text-slate-800"}>{text}</span>
    </label>
  );

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="no-print flex items-center justify-between">
        <Link to={`/auto/${l.id}`} className="text-sm text-brand-700 hover:underline">← Terug naar de auto</Link>
        <Button variant="secondary" onClick={() => window.print()}><Printer className="h-4 w-4" /> Printen</Button>
      </div>
      <div>
        <h1 className="text-2xl font-bold">Checklist bezichtiging</h1>
        <p className="text-slate-600">{l.title} · {l.year} · {km(l.mileage_km)} · {euro(l.price_eur)} {l.kenteken && `· ${l.kenteken}`}</p>
        <p className="no-print mt-1 text-sm text-slate-500">{done} van {all.length} punten afgevinkt{watch ? " · opgeslagen bij je favoriet" : " · opgeslagen op dit apparaat"}</p>
      </div>
      {model_issues.length > 0 && (
        <div className="print-break rounded-xl border border-amber-200 bg-amber-50 p-5">
          <h2 className="mb-2 font-semibold text-amber-900">Modelspecifiek: vraag hiernaar</h2>
          <div className="space-y-4">
            {model_issues.map((m) => (
              <div key={m.title}>
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <Badge tone={severityTone(m.severity)}>{m.severity}</Badge>
                  <span className="font-medium">{m.title}</span>
                  {m.recall_status === "hersteld" && <Badge tone="good">recall uitgevoerd</Badge>}
                  {m.recall_status === "open" && <Badge tone="bad">recall open</Badge>}
                  {m.certainty !== "zeker" && <span className="text-xs text-slate-500">({m.certainty})</span>}
                </div>
                {[...m.questions, ...m.verify, ...m.test_drive].map((t) => <Item key={t} k={`${m.title}|${t}`} text={t} />)}
              </div>
            ))}
          </div>
        </div>
      )}
      {sections.map((s) => (
        <div key={s.title} className="print-break rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-2 font-semibold">{s.title}</h2>
          {s.items.map((t) => <Item key={t} k={`${s.title}|${t}`} text={t} />)}
        </div>
      ))}
    </div>
  );
}
