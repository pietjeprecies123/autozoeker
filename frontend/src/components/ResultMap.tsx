import "leaflet/dist/leaflet.css";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import { Link } from "react-router-dom";
import { dealLabel, euro, km } from "../lib/format";
import type { ListingCard } from "../lib/types";

function colour(deal: number | null) {
  if (deal == null) return "#64748b";
  if (deal >= 0.05) return "#059669";
  if (deal > -0.03) return "#d97706";
  return "#e11d48";
}

export default function ResultMap({ items }: { items: ListingCard[] }) {
  const pts = items.filter((i) => i.lat != null && i.lon != null);
  return (
    <div className="h-[600px] overflow-hidden rounded-xl border border-slate-200">
      <MapContainer center={[52.13, 5.29]} zoom={7} scrollWheelZoom className="h-full w-full">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {pts.map((l) => (
          <CircleMarker
            key={l.id}
            center={[l.lat!, l.lon!]}
            radius={6 + Math.round((l.match ?? 50) / 25)}
            pathOptions={{ color: "white", weight: 1.5, fillColor: colour(l.deal_score), fillOpacity: 0.85 }}
          >
            <Popup>
              <div className="space-y-1 text-sm">
                <Link to={`/auto/${l.id}`} className="font-semibold text-brand-700">
                  {l.title}
                </Link>
                <div>
                  {euro(l.price_eur)} · {l.year} · {km(l.mileage_km)}
                </div>
                <div className="text-xs text-slate-500">
                  {dealLabel(l.deal_score).text} · match {l.match}
                </div>
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
