import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellRing, CheckCheck, Sparkles } from "lucide-react";
import { useEffect } from "react";
import { Link } from "react-router-dom";
import { ListingRow } from "../components/car";
import { Badge, Button, Empty, ErrorBox, Section, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { date, euro } from "../lib/format";
import { useApp } from "../lib/store";

const KIND: Record<string, { label: string; tone: "good" | "info" | "warn" | "ok" }> = {
  new: { label: "Nieuw", tone: "good" },
  price_drop: { label: "Prijsdaling", tone: "info" },
  back: { label: "Weer online", tone: "warn" },
  sold: { label: "Verkocht/offline", tone: "ok" },
};

export default function ForYouPage() {
  const { profileId } = useApp();
  const qc = useQueryClient();
  const feed = useQuery({ queryKey: ["feed", profileId], queryFn: () => api.feed(profileId!), enabled: !!profileId });
  const alerts = useQuery({ queryKey: ["alerts", profileId], queryFn: () => api.alerts(profileId!), enabled: !!profileId });
  const seen = useMutation({ mutationFn: () => api.markAlertsSeen(profileId!), onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }) });
  const watch = useMutation({
    mutationFn: (id: number) => api.addWatch(id, profileId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["feed"] }),
  });
  useEffect(() => {
    if (alerts.data && alerts.data.unseen > 0) {
      const t = setTimeout(() => seen.mutate(), 4000);
      return () => clearTimeout(t);
    }
  }, [alerts.data?.unseen]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!profileId) return <Spinner label="Kies eerst een profiel" />;
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      <div className="space-y-4">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold"><Sparkles className="h-5 w-5 text-brand-700" />Nieuw voor jou</h1>
          <p className="text-sm text-slate-600">Auto's van de afgelopen 7 dagen die passen bij je zoekopdrachten of lijken op auto's die je bewaarde of leuk vond.</p>
        </div>
        {feed.error && <ErrorBox error={feed.error} />}
        {feed.isLoading && <Spinner />}
        {feed.data && feed.data.items.length === 0 && (
          <Empty title="Nog niets nieuws">
            Bewaar een zoekopdracht (knop "Bewaar &amp; volg" bij Zoeken) of geef duimpjes aan auto's. Nieuwe advertenties die passen verschijnen dan hier, en optioneel als
            pushmelding op je telefoon.
          </Empty>
        )}
        <div className="space-y-3">
          {feed.data?.items.map((l) => <ListingRow key={l.id} l={l} onWatch={(id) => watch.mutate(id)} />)}
        </div>
      </div>
      <aside>
        <Section
          title="Meldingen"
          icon={<BellRing className="h-5 w-5 text-brand-700" />}
          actions={
            alerts.data && alerts.data.unseen > 0 ? (
              <Button size="sm" variant="ghost" onClick={() => seen.mutate()}><CheckCheck className="h-4 w-4" />Gelezen</Button>
            ) : null
          }
        >
          {alerts.isLoading && <Spinner />}
          {alerts.data && alerts.data.items.length === 0 && <p className="text-sm text-slate-500">Nog geen meldingen.</p>}
          <ol className="space-y-3">
            {alerts.data?.items.map((a) => (
              <li key={a.id} className={`rounded-lg border p-3 text-sm ${a.seen ? "border-slate-200" : "border-brand-300 bg-brand-50/50"}`}>
                <div className="flex items-center justify-between gap-2">
                  <Badge tone={KIND[a.kind]?.tone ?? "ok"}>{KIND[a.kind]?.label ?? a.kind}</Badge>
                  <span className="text-xs text-slate-400">{date(a.created_at)}</span>
                </div>
                <Link to={`/auto/${a.listing.id}`} className="mt-1 block font-medium text-slate-900 hover:text-brand-700">{a.listing.title}</Link>
                <div className="num text-xs text-slate-600">
                  {euro(a.price_eur)} {a.match != null && `· match ${a.match}`} {a.search && `· ${a.search}`}
                </div>
                <div className="mt-1 text-[11px] text-slate-400">
                  {a.delivery === "sent" ? "Push verstuurd" : a.delivery === "digest" ? "In dagoverzicht" : a.delivery === "skipped" ? "Alleen in app" : a.delivery === "failed" ? "Push mislukt" : "In wachtrij"}
                </div>
              </li>
            ))}
          </ol>
        </Section>
      </aside>
    </div>
  );
}
