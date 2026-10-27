import { euro } from "../lib/format";

/** Horizontal band: market value range (p10–p90) with markers for estimate and asking price. */
export default function ValueBand({ low, mid, high, price }: { low: number; mid: number; high: number; price: number }) {
  const min = Math.min(low, price) * 0.95;
  const max = Math.max(high, price) * 1.05;
  const pos = (v: number) => `${((v - min) / (max - min)) * 100}%`;
  const good = price <= mid;
  return (
    <div className="pt-6 pb-8">
      <div className="relative h-3 rounded-full bg-slate-100">
        <div className="absolute inset-y-0 rounded-full bg-gradient-to-r from-emerald-200 via-amber-100 to-rose-200" style={{ left: pos(low), width: `calc(${pos(high)} - ${pos(low)})` }} />
        <div className="absolute -top-1 h-5 w-0.5 bg-slate-500" style={{ left: pos(mid) }} />
        <div className="absolute -top-6 -translate-x-1/2 whitespace-nowrap text-xs text-slate-500" style={{ left: pos(mid) }}>
          markt {euro(mid)}
        </div>
        <div
          className={`absolute -top-1.5 h-6 w-6 -translate-x-1/2 rounded-full border-2 border-white shadow ${good ? "bg-emerald-600" : "bg-rose-600"}`}
          style={{ left: pos(price) }}
          title={`Vraagprijs ${euro(price)}`}
        />
        <div className="num absolute top-6 -translate-x-1/2 whitespace-nowrap text-xs font-semibold text-slate-800" style={{ left: pos(price) }}>
          vraagprijs {euro(price)}
        </div>
      </div>
      <div className="num mt-9 flex justify-between text-[11px] text-slate-400">
        <span>{euro(low)} (laag)</span>
        <span>{euro(high)} (hoog)</span>
      </div>
    </div>
  );
}
