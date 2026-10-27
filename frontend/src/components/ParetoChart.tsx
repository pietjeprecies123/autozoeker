import { useNavigate } from "react-router-dom";
import { CartesianGrid, Line, ResponsiveContainer, Scatter, ComposedChart, Tooltip, XAxis, YAxis } from "recharts";
import { euro, km } from "../lib/format";
import type { ParetoPoint } from "../lib/types";

function TooltipBox({ active, payload }: { active?: boolean; payload?: { payload: ParetoPoint }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  if (!p.title) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow">
      <div className="font-semibold text-slate-900">{p.title}</div>
      <div className="num">
        {euro(p.price)} · {km(p.km)} · {p.year}
      </div>
      <div className="text-slate-500">
        match {p.match}
        {p.deal_score != null && ` · ${Math.round(p.deal_score * 100)}% t.o.v. markt`}
        {p.frontier && " · op de efficiënte grens"}
      </div>
    </div>
  );
}

export default function ParetoChart({ points }: { points: ParetoPoint[] }) {
  const navigate = useNavigate();
  const frontier = points.filter((p) => p.frontier).sort((a, b) => a.price - b.price);
  const rest = points.filter((p) => !p.frontier);
  return (
    <div>
      <p className="mb-3 text-sm text-slate-600">
        Elke stip is een auto. De <span className="font-semibold text-brand-700">groene lijn</span> verbindt de auto's waarvoor geen andere auto bestaat die
        zowel goedkoper is als minder kilometers heeft – de beste prijs/km-verhouding binnen je zoekopdracht. Klik op een stip om de auto te openen.
      </p>
      <div className="h-[520px] rounded-xl border border-slate-200 bg-white p-3">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart margin={{ top: 10, right: 20, bottom: 30, left: 20 }}>
            <CartesianGrid stroke="#e2e8f0" />
            <XAxis
              type="number"
              dataKey="km"
              name="Kilometerstand"
              tickFormatter={(v) => `${Math.round(v / 1000)}k`}
              label={{ value: "Kilometerstand", position: "insideBottom", offset: -15, fill: "#64748b", fontSize: 12 }}
              domain={["auto", "auto"]}
            />
            <YAxis
              type="number"
              dataKey="price"
              name="Prijs"
              tickFormatter={(v) => `€${Math.round(v / 1000)}k`}
              label={{ value: "Vraagprijs", angle: -90, position: "insideLeft", fill: "#64748b", fontSize: 12 }}
              domain={["auto", "auto"]}
            />
            <Tooltip content={<TooltipBox />} />
            <Scatter
              data={rest}
              fill="#94a3b8"
              fillOpacity={0.55}
              onClick={(d: unknown) => navigate(`/auto/${(d as { payload?: ParetoPoint }).payload?.id ?? (d as ParetoPoint).id}`)}
              cursor="pointer"
            />
            <Line data={frontier} type="stepAfter" dataKey="price" stroke="#059669" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Scatter
              data={frontier}
              fill="#059669"
              onClick={(d: unknown) => navigate(`/auto/${(d as { payload?: ParetoPoint }).payload?.id ?? (d as ParetoPoint).id}`)}
              cursor="pointer"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
