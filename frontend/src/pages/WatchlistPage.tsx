import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { ClipboardCheck, Heart, StickyNote, Trash2, TrendingDown } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { CarImage, DealBadge } from "../components/car";
import { Badge, Empty, ErrorBox, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { euro, km } from "../lib/format";
import { useApp } from "../lib/store";
import type { WatchItem } from "../lib/types";

const LABELS: Record<string, string> = {
  interessant: "Interessant",
  gebeld: "Gebeld / gemaild",
  bezichtiging: "Bezichtiging gepland",
  proefrit: "Proefrit gedaan",
  bod: "Bod gedaan",
  gekocht: "Gekocht 🎉",
  afgevallen: "Afgevallen",
};

function WatchCard({ item, onMove, onDelete, onNotes }: { item: WatchItem; onMove: (s: string) => void; onDelete: () => void; onNotes: (n: string) => void }) {
  const { meta } = useApp();
  const [editing, setEditing] = useState(false);
  const [notes, setNotes] = useState(item.watch.notes);
  const drop = item.watch.price_at_add && item.price_eur ? item.watch.price_at_add - item.price_eur : 0;
  const addedBy = meta?.profiles.find((p) => p.id === item.watch.added_by)?.name;
  return (
    <div
      draggable
      onDragStart={(e) => e.dataTransfer.setData("text/plain", String(item.watch.id))}
      className={clsx("cursor-grab rounded-lg border border-slate-200 bg-white p-2.5 shadow-sm active:cursor-grabbing", item.status !== "active" && "opacity-60")}
    >
      <Link to={`/auto/${item.id}`} className="block h-24 overflow-hidden rounded-md bg-slate-100">
        <CarImage listing={item} />
      </Link>
      <Link to={`/auto/${item.id}`} className="mt-2 line-clamp-2 block text-sm font-medium text-slate-900 hover:text-brand-700">{item.title}</Link>
      <div className="num mt-0.5 text-xs text-slate-500">{item.year} · {km(item.mileage_km)}</div>
      <div className="mt-1 flex items-center justify-between">
        <span className="num font-semibold">{euro(item.price_eur)}</span>
        {drop > 0 && <Badge tone="good"><TrendingDown className="h-3 w-3" />−{euro(drop)}</Badge>}
      </div>
      <div className="mt-1 flex flex-wrap gap-1">
        <DealBadge deal={item.deal_score} />
        {item.status !== "active" && <Badge tone="bad">Offline</Badge>}
        {item.is_demo && <Badge tone="demo">DEMO</Badge>}
      </div>
      {editing ? (
        <textarea
          autoFocus
          className="mt-2 w-full rounded border border-slate-300 p-1.5 text-xs"
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={() => {
            setEditing(false);
            if (notes !== item.watch.notes) onNotes(notes);
          }}
        />
      ) : (
        item.watch.notes && <p className="mt-2 whitespace-pre-line rounded bg-amber-50 p-1.5 text-xs text-amber-900">{item.watch.notes}</p>
      )}
      <div className="mt-2 flex items-center justify-between text-slate-400">
        <span className="text-[10px]">{addedBy ? `door ${addedBy}` : ""}</span>
        <div className="flex gap-1">
          <button onClick={() => setEditing(true)} className="rounded p-1 hover:bg-slate-100 hover:text-slate-700" title="Notitie"><StickyNote className="h-3.5 w-3.5" /></button>
          <Link to={`/auto/${item.id}/checklist`} className="rounded p-1 hover:bg-slate-100 hover:text-slate-700" title="Checklist"><ClipboardCheck className="h-3.5 w-3.5" /></Link>
          <button onClick={onDelete} className="rounded p-1 hover:bg-rose-50 hover:text-rose-600" title="Verwijderen"><Trash2 className="h-3.5 w-3.5" /></button>
        </div>
      </div>
      <select
        value={item.watch.status}
        onChange={(e) => onMove(e.target.value)}
        className="mt-2 w-full rounded border border-slate-200 px-1.5 py-1 text-xs sm:hidden"
        aria-label="Status"
      >
        {Object.entries(LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
      </select>
    </div>
  );
}

export default function WatchlistPage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["watchlist"], queryFn: api.watchlist });
  const [over, setOver] = useState<string | null>(null);
  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: { status?: string; notes?: string } }) => api.updateWatch(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlist"] }),
  });
  const remove = useMutation({ mutationFn: (id: number) => api.deleteWatch(id), onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlist"] }) });

  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBox error={q.error} />;
  if (q.data.items.length === 0) {
    return (
      <Empty title="Nog geen favorieten" icon={<Heart className="h-8 w-8 text-rose-400" />}>
        Klik op het hartje bij een auto. Hier volg je ze daarna van "interessant" tot "gekocht", met notities en de bezichtigingschecklist. Prijsdalingen en verkochte auto's krijg
        je als melding.
      </Empty>
    );
  }
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold">Favorieten</h1>
        <p className="text-sm text-slate-600">Gedeeld tussen jullie profielen. Sleep kaarten tussen kolommen.</p>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-4">
        {q.data.statuses.map((s) => {
          const items = q.data!.items.filter((i) => i.watch.status === s);
          return (
            <div
              key={s}
              onDragOver={(e) => {
                e.preventDefault();
                setOver(s);
              }}
              onDragLeave={() => setOver(null)}
              onDrop={(e) => {
                e.preventDefault();
                setOver(null);
                const id = Number(e.dataTransfer.getData("text/plain"));
                if (id) update.mutate({ id, body: { status: s } });
              }}
              className={clsx("w-60 shrink-0 rounded-xl border p-2", over === s ? "border-brand-400 bg-brand-50" : "border-slate-200 bg-slate-100/60")}
            >
              <div className="mb-2 flex items-center justify-between px-1 text-sm font-medium text-slate-700">
                {LABELS[s] ?? s}
                <span className="num rounded-full bg-white px-2 text-xs text-slate-500">{items.length}</span>
              </div>
              <div className="space-y-2">
                {items.map((i) => (
                  <WatchCard
                    key={i.watch.id}
                    item={i}
                    onMove={(st) => update.mutate({ id: i.watch.id, body: { status: st } })}
                    onDelete={() => remove.mutate(i.watch.id)}
                    onNotes={(n) => update.mutate({ id: i.watch.id, body: { notes: n } })}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
