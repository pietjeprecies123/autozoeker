from __future__ import annotations

import csv
import io

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import DB
from app.api.serialize import plate_display, scored_card
from app.config import get_settings
from app.knowledge.service import coverage
from app.models import Profile, WatchlistItem
from app.normalize.fields import BODY_LABELS, FUEL_LABELS, OPTION_LABELS
from app.normalize.taxonomy import catalog
from app.scoring.components import COMPONENT_LABELS, DEFAULT_WEIGHTS
from app.search import SearchRequest, pareto_points, run_search, summarize
from app.sources.registry import adapters_info
from app.state import STATE

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/meta")
def meta(session: Session = DB):
    settings = get_settings()
    profiles = [
        {"id": p.id, "name": p.name, "home_postcode": p.home_postcode, "has_ntfy": bool(p.ntfy_topic or settings.ntfy_topic)}
        for p in session.scalars(select(Profile).order_by(Profile.id))
    ]
    return {
        "catalog": catalog(),
        "fuels": FUEL_LABELS,
        "bodies": BODY_LABELS,
        "transmissions": {"handgeschakeld": "Handgeschakeld", "automaat": "Automaat"},
        "options": OPTION_LABELS,
        "colours": ["zwart", "wit", "grijs", "zilver", "blauw", "rood", "groen", "geel", "oranje", "bruin", "paars"],
        "weights": DEFAULT_WEIGHTS,
        "weight_labels": COMPONENT_LABELS,
        "sources": adapters_info(),
        "demo_mode": settings.demo_mode,
        "ai_enabled": settings.ai_enabled,
        "ntfy_configured": bool(settings.ntfy_topic) or any(p["has_ntfy"] for p in profiles),
        "home_postcode": settings.home_postcode,
        "profiles": profiles,
        "issue_coverage": coverage(),
        "ready": STATE["ready"],
        "startup_message": STATE["message"],
    }


@router.post("/search")
def search(req: SearchRequest, session: Session = DB):
    scored = run_search(session, req)
    total = len(scored)
    start = max(0, (req.page - 1) * req.page_size)
    page = scored[start:start + req.page_size]
    watched = {w.listing_id for w in session.scalars(select(WatchlistItem))}
    return {
        "total": total,
        "page": req.page,
        "page_size": req.page_size,
        "items": [scored_card(s, {"on_watchlist": s.listing.id in watched}) for s in page],
        "stats": summarize(scored),
        "pareto": pareto_points(scored),
    }


@router.post("/search/export.csv")
def export_csv(req: SearchRequest, session: Session = DB):
    scored = run_search(session, req)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow([
        "id", "titel", "merk", "model", "generatie", "bouwjaar", "km", "prijs", "marktwaarde", "deal_pct", "match",
        "brandstof", "transmissie", "carrosserie", "kw", "kenteken", "verkoper", "plaats", "afstand_km", "bron", "url",
        "dagen_online", "rode_vlaggen",
    ])
    for s in scored:
        x = s.listing
        w.writerow([
            x.id, x.title, x.make, x.model, x.generation, x.year, x.mileage_km, x.price_eur, x.predicted_price,
            round(x.deal_score * 100, 1) if x.deal_score is not None else "", s.match, x.fuel, x.transmission, x.body,
            x.power_kw, plate_display(x.kenteken), x.seller_name, x.city or x.postcode, s.distance_km, x.source, x.url,
            (x.last_seen_at - x.first_seen_at).days if x.first_seen_at and x.last_seen_at else "",
            "|".join(f["title"] for f in (x.red_flags or [])),
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=autozoeker-export.csv"},
    )
