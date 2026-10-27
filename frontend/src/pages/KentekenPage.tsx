import { useQuery } from "@tanstack/react-query";
import { RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import IssueCard from "../components/IssueCard";
import RdwReport from "../components/RdwReport";
import { Badge, Button, Card, ErrorBox, Section, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { date, euro, km } from "../lib/format";

export default function KentekenPage() {
  const { plate } = useParams();
  const navigate = useNavigate();
  const [input, setInput] = useState(plate ?? "");
  const [refresh, setRefresh] = useState(false);
  const q = useQuery({ queryKey: ["kenteken", plate, refresh], queryFn: () => api.kenteken(plate!, refresh), enabled: !!plate });

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-bold"><ShieldCheck className="h-5 w-5 text-brand-700" />Kenteken-check</h1>
        <p className="text-sm text-slate-600">
          Gratis check via RDW Open Data: APK, NAP-tellerstandoordeel, import, terugroepacties (open of hersteld), eerdere APK-gebreken, trekgewicht en meer. Plus de
          advertentiegeschiedenis van dit kenteken in Autozoeker.
        </p>
      </div>
      <Card className="p-4">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (input.trim()) navigate(`/kenteken/${input.trim().toUpperCase()}`);
          }}
        >
          <div className="flex flex-1 items-stretch overflow-hidden rounded-lg border-2 border-slate-800">
            <span className="flex items-center bg-blue-700 px-2 text-xs font-bold text-yellow-300">NL</span>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="AB-123-C"
              className="w-full bg-yellow-300 px-3 py-2 text-lg font-bold uppercase tracking-widest text-slate-900 placeholder:text-yellow-700/60 focus:outline-none"
              aria-label="Kenteken"
            />
          </div>
          <Button type="submit">Check</Button>
        </form>
      </Card>
      {plate && q.isLoading && <Spinner label="RDW raadplegen…" />}
      {q.error && <ErrorBox error={q.error} />}
      {q.data && (
        <>
          {!q.data.vehicle ? (
            <Card className="p-5 text-sm text-slate-600">
              RDW Open Data is nu niet bereikbaar en er zijn nog geen opgeslagen gegevens voor {q.data.kenteken}. Probeer het later opnieuw.
            </Card>
          ) : (
            <Section
              title={`RDW-gegevens ${q.data.kenteken}`}
              actions={!q.data.vehicle.is_demo && <Button size="sm" variant="ghost" onClick={() => setRefresh(true)}><RefreshCw className="h-4 w-4" />Vernieuw</Button>}
            >
              <RdwReport v={q.data.vehicle} />
            </Section>
          )}
          {q.data.issues.length > 0 && (
            <Section title="Bekende aandachtspunten voor dit model">
              <div className="space-y-2">{q.data.issues.map((i) => <IssueCard key={i.id} issue={i} />)}</div>
            </Section>
          )}
          <Section title="Advertentiegeschiedenis">
            {q.data.listings.length === 0 ? (
              <p className="text-sm text-slate-500">Dit kenteken is (nog) niet in advertenties gezien door Autozoeker.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {q.data.listings.map((l) => (
                  <li key={l.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-3">
                    <div>
                      <Link to={`/auto/${l.id}`} className="font-medium text-slate-900 hover:text-brand-700">{l.title}</Link>
                      <div className="text-xs text-slate-500">
                        {l.source_label} · {date(l.first_seen_at)} – {l.removed_at ? date(l.removed_at) : "nu"} · {km(l.mileage_km)}
                      </div>
                    </div>
                    <div className="num text-right">
                      <div className="font-semibold">{euro(l.price_eur)}</div>
                      {l.price_history.length > 1 && <div className="text-xs text-slate-500">start {euro(l.price_history[0].price)}</div>}
                    </div>
                    {l.status !== "active" && <Badge tone="ok">offline</Badge>}
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </>
      )}
    </div>
  );
}
