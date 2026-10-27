import clsx from "clsx";
import { AlertTriangle, BadgeCheck, Calendar, Fuel, Gauge, GitCompare, Heart, MapPin, ShieldAlert, TrendingDown, Wrench } from "lucide-react";
import { Link } from "react-router-dom";
import { dealLabel, euro, km } from "../lib/format";
import { useApp } from "../lib/store";
import type { ListingCard, RedFlag } from "../lib/types";
import { Badge, severityTone } from "./ui";

const MAKE_COLOURS = ["#0f766e", "#1d4ed8", "#7c3aed", "#be123c", "#b45309", "#15803d", "#0369a1", "#4338ca"];

function hash(s: string) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

export function CarImage({ listing, className }: { listing: Pick<ListingCard, "image_url" | "make_name" | "model_name" | "body" | "title">; className?: string }) {
  if (listing.image_url) {
    return <img src={listing.image_url} alt={listing.title} loading="lazy" className={clsx("h-full w-full object-cover", className)} />;
  }
  const colour = MAKE_COLOURS[hash(listing.make_name || listing.title) % MAKE_COLOURS.length];
  const tall = listing.body === "suv" || listing.body === "mpv";
  return (
    <div className={clsx("relative flex h-full w-full items-center justify-center overflow-hidden", className)} style={{ background: `linear-gradient(135deg, ${colour}22, ${colour}44)` }}>
      <svg viewBox="0 0 120 60" className="w-3/4 opacity-80" aria-hidden>
        <path
          d={
            tall
              ? "M8 42 L14 26 Q17 18 26 18 L86 18 Q96 18 101 26 L112 42 L112 48 Q112 50 110 50 L10 50 Q8 50 8 48 Z"
              : "M6 42 L18 30 Q24 24 34 23 L70 22 Q82 22 92 30 L110 36 Q114 38 114 42 L114 48 Q114 50 112 50 L8 50 Q6 50 6 48 Z"
          }
          fill={colour}
        />
        <circle cx="30" cy="50" r="8" fill="#1e293b" />
        <circle cx="90" cy="50" r="8" fill="#1e293b" />
        <circle cx="30" cy="50" r="3.5" fill="#cbd5e1" />
        <circle cx="90" cy="50" r="3.5" fill="#cbd5e1" />
      </svg>
      <span className="absolute bottom-1.5 left-2 text-[10px] font-semibold uppercase tracking-wide" style={{ color: colour }}>
        {listing.make_name}
      </span>
    </div>
  );
}

export function ScoreRing({ value, size = 44, label = "match" }: { value: number | null | undefined; size?: number; label?: string }) {
  const v = value ?? 0;
  const r = (size - 6) / 2;
  const c = 2 * Math.PI * r;
  const colour = v >= 75 ? "#059669" : v >= 55 ? "#d97706" : "#e11d48";
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} title={`Match-score ${v}/100`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="#e2e8f0" strokeWidth="5" fill="none" />
        <circle cx={size / 2} cy={size / 2} r={r} stroke={colour} strokeWidth="5" fill="none" strokeDasharray={c} strokeDashoffset={c * (1 - v / 100)} strokeLinecap="round" />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center leading-none">
        <span className="num text-sm font-bold text-slate-900">{value ?? "–"}</span>
        {size >= 52 && <span className="text-[9px] uppercase text-slate-500">{label}</span>}
      </div>
    </div>
  );
}

export function DealBadge({ deal, confidence, eur }: { deal: number | null; confidence?: string | null; eur?: number | null }) {
  const d = dealLabel(deal);
  const tone = d.tone === "good" ? "good" : d.tone === "bad" ? "bad" : d.tone === "none" ? "none" : "ok";
  return (
    <Badge tone={tone} title={confidence ? `Betrouwbaarheid schatting: ${confidence}` : undefined}>
      {d.tone === "good" && <TrendingDown className="h-3 w-3" />}
      {d.text}
      {eur != null && d.tone !== "ok" && d.tone !== "none" && <span className="opacity-70">({euro(Math.abs(eur))})</span>}
      {confidence === "low" && <span className="opacity-60">~</span>}
    </Badge>
  );
}

export function FlagChips({ flags, max = 3 }: { flags: RedFlag[]; max?: number }) {
  const shown = flags.filter((f) => f.severity !== "info").slice(0, max);
  if (!shown.length) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {shown.map((f) => (
        <Badge key={f.code} tone={severityTone(f.severity)} title={f.detail}>
          <AlertTriangle className="h-3 w-3" />
          {f.title}
        </Badge>
      ))}
    </div>
  );
}

export function ListingRow({ l, onWatch }: { l: ListingCard; onWatch?: (id: number) => void }) {
  const { compare, toggleCompare } = useApp();
  const inCompare = compare.includes(l.id);
  return (
    <div className="group relative flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm transition hover:shadow-md sm:flex-row">
      <Link to={`/auto/${l.id}`} className="block h-40 shrink-0 bg-slate-100 sm:h-auto sm:w-56">
        <CarImage listing={l} />
      </Link>
      <div className="flex min-w-0 flex-1 flex-col gap-2 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <Link to={`/auto/${l.id}`} className="line-clamp-1 font-semibold text-slate-900 hover:text-brand-700">
              {l.title}
            </Link>
            <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-slate-500">
              <span className="flex items-center gap-1"><Calendar className="h-3 w-3" />{l.year ?? "–"}</span>
              <span className="flex items-center gap-1"><Gauge className="h-3 w-3" />{km(l.mileage_km)}</span>
              <span className="flex items-center gap-1"><Fuel className="h-3 w-3" />{l.fuel_label ?? "–"}</span>
              {l.transmission && <span>{l.transmission === "automaat" ? "Automaat" : "Handgeschakeld"}</span>}
              {l.power_pk && <span>{l.power_pk} pk</span>}
              <span className="flex items-center gap-1">
                <MapPin className="h-3 w-3" />
                {l.city || (l.postcode ? `PC ${l.postcode}` : "–")}
                {l.distance_km != null && <span>· {Math.round(l.distance_km)} km</span>}
              </span>
            </div>
          </div>
          <ScoreRing value={l.match} />
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <DealBadge deal={l.deal_score} confidence={l.valuation_confidence} eur={l.deal_eur} />
          {l.seller_bovag && <Badge tone="brand"><BadgeCheck className="h-3 w-3" />BOVAG</Badge>}
          {l.warranty_months ? <Badge tone="brand">{l.warranty_months} mnd garantie</Badge> : null}
          {l.issue_count > 0 && (
            <Badge tone="warn" title="Bekende modelspecifieke aandachtspunten">
              <Wrench className="h-3 w-3" />
              {l.issue_count} aandachtspunt{l.issue_count > 1 ? "en" : ""}
            </Badge>
          )}
          {l.rdw?.odometer_judgement && l.rdw.odometer_judgement.toLowerCase().startsWith("logisch") && <Badge tone="good">NAP logisch</Badge>}
          {l.price_drops > 0 && <Badge tone="info">{l.price_drops}× prijs verlaagd</Badge>}
          {l.is_demo && <Badge tone="demo">DEMO</Badge>}
          {l.duplicates.length > 0 && <Badge tone="ok">Ook op {l.duplicates.map((d) => d.source_label).join(", ")}</Badge>}
        </div>
        <FlagChips flags={l.red_flags} />
        {l.reasons && l.reasons.length > 0 && <div className="text-xs text-brand-800">{l.reasons.slice(0, 2).join(" · ")}</div>}
        <div className="mt-auto flex items-end justify-between gap-3 pt-1">
          <div>
            <div className="num text-xl font-bold text-slate-900">{euro(l.price_eur)}</div>
            {l.predicted_price && (
              <div className="num text-xs text-slate-500">
                Marktwaarde ≈ {euro(l.predicted_price)} <span className="opacity-70">({euro(l.predicted_low)}–{euro(l.predicted_high)})</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => toggleCompare(l.id)}
              className={clsx("rounded-lg p-2 text-sm", inCompare ? "bg-brand-100 text-brand-800" : "text-slate-500 hover:bg-slate-100")}
              title={inCompare ? "Uit vergelijking" : "Vergelijken"}
              aria-pressed={inCompare}
            >
              <GitCompare className="h-4 w-4" />
            </button>
            {onWatch && (
              <button
                onClick={() => onWatch(l.id)}
                className={clsx("rounded-lg p-2", l.on_watchlist ? "text-rose-600" : "text-slate-500 hover:bg-slate-100")}
                title={l.on_watchlist ? "Op je favorieten" : "Bewaar als favoriet"}
              >
                <Heart className={clsx("h-4 w-4", l.on_watchlist && "fill-rose-600")} />
              </button>
            )}
          </div>
        </div>
      </div>
      {l.rdw?.open_recall && (
        <div className="absolute left-2 top-2"><Badge tone="bad"><ShieldAlert className="h-3 w-3" />Recall open</Badge></div>
      )}
    </div>
  );
}
