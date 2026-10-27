from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.analysis import ensure_model, refresh
from app.api.deps import DB, get_listing, get_profile, get_vehicle
from app.api.serialize import card
from app.config import get_settings
from app.enrich.geo import haversine_km, road_km
from app.enrich.rdw import enrich, vehicle_to_dict
from app.ingest.pipeline import upsert
from app.knowledge import checklist as checklist_mod
from app.knowledge import ev as ev_mod
from app.knowledge.service import issues_for, model_overview
from app.models import Feedback, Listing, PriceHistory, Vehicle, WatchlistItem
from app.scoring.components import composite
from app.scoring.negotiation import advise
from app.search import home_location
from app.sources.registry import adapter_for_url
from app.tco.tco import TcoInput
from app.tco.tco import compute as tco_compute
from app.valuation.model import nearest

router = APIRouter(prefix="/api", tags=["listings"])


def _comparables(session: Session, listing: Listing, k: int = 12) -> list[Listing]:
    if not listing.make or not listing.model:
        return []
    pool = list(session.scalars(
        select(Listing).options(selectinload(Listing.prices))
        .where(Listing.make == listing.make, Listing.model == listing.model, Listing.id != listing.id)
        .limit(1500)
    ))
    return nearest(listing, pool, k=k)


def _distance(session: Session, listing: Listing, profile_id: int | None) -> float | None:
    profile = get_profile(session, profile_id) if profile_id else None
    home = home_location(session, profile)
    if home and listing.lat is not None and listing.lon is not None:
        return round(road_km(haversine_km(home[0], home[1], listing.lat, listing.lon)), 1)
    return None


@router.get("/listings/{listing_id}")
def listing_detail(listing_id: int, profile_id: int | None = None, session: Session = DB):
    listing = get_listing(session, listing_id)
    vehicle = get_vehicle(session, listing)
    if listing.valued_at is None:
        refresh(session, [listing.id])
    distance = _distance(session, listing, profile_id)
    profile = get_profile(session, profile_id) if profile_id else None
    match = composite(listing.score_components or {}, profile.weights if profile else None, distance)
    issues = issues_for(listing, vehicle)
    comps = _comparables(session, listing)
    model = ensure_model(session)
    duplicates = []
    if listing.group_id:
        duplicates = list(session.scalars(select(Listing).where(Listing.group_id == listing.group_id, Listing.id != listing.id)))
    watch = session.scalar(select(WatchlistItem).where(WatchlistItem.listing_id == listing.id))
    feedback = session.scalar(select(Feedback).where(Feedback.listing_id == listing.id, Feedback.profile_id == (profile.id if profile else -1)))
    out = card(listing, vehicle, distance, match, duplicates)
    out.update({
        "description": listing.description,
        "image_urls": listing.image_urls or [],
        "price_history": [{"date": p.observed_at, "price": p.price_eur} for p in listing.prices],
        "vehicle": vehicle_to_dict(vehicle),
        "issues": [m.to_dict() for m in issues],
        "model_overview": model_overview(listing.make, listing.model) if listing.make and listing.model else None,
        "comparables": [card(c) for c in comps],
        "depreciation": model.depreciation_curve(listing) if model else [],
        "negotiation": advise(listing, vehicle, issues, comps),
        "ev": ev_mod.info(listing, vehicle),
        "watchlist": {"id": watch.id, "status": watch.status, "notes": watch.notes} if watch else None,
        "feedback": feedback.value if feedback else 0,
        "valuation_metrics": model.metrics if model else {},
    })
    return out


@router.get("/listings/{listing_id}/checklist")
def listing_checklist(listing_id: int, session: Session = DB):
    listing = get_listing(session, listing_id)
    vehicle = get_vehicle(session, listing)
    issues = issues_for(listing, vehicle)
    return {"listing": card(listing, vehicle), **checklist_mod.build(listing, vehicle, issues)}


@router.post("/listings/{listing_id}/tco")
def listing_tco(listing_id: int, inp: TcoInput, profile_id: int | None = None, session: Session = DB):
    listing = get_listing(session, listing_id)
    vehicle = get_vehicle(session, listing)
    profile = get_profile(session, profile_id) if profile_id else None
    model = ensure_model(session)

    def resale(years, km_per_year):
        return model.project_value(listing, years, km_per_year) if model else None

    postcode = (profile.home_postcode if profile else None) or get_settings().home_postcode
    return tco_compute(listing, vehicle, inp, postcode, resale)


class FeedbackIn(BaseModel):
    profile_id: int
    value: int  # +1, -1, 0 (clear)


@router.post("/listings/{listing_id}/feedback")
def listing_feedback(listing_id: int, body: FeedbackIn, session: Session = DB):
    from app.feed import learn_weights

    get_listing(session, listing_id)
    fb = session.scalar(select(Feedback).where(Feedback.listing_id == listing_id, Feedback.profile_id == body.profile_id))
    if body.value == 0:
        if fb:
            session.delete(fb)
    elif fb:
        fb.value = 1 if body.value > 0 else -1
    else:
        session.add(Feedback(listing_id=listing_id, profile_id=body.profile_id, value=1 if body.value > 0 else -1))
    session.flush()
    learned = learn_weights(session, body.profile_id)
    return {"ok": True, "learned_weights": learned}


class CompareIn(BaseModel):
    ids: list[int]
    profile_id: int | None = None
    km_per_year: int = 13000


@router.post("/compare")
def compare(body: CompareIn, session: Session = DB):
    if not 1 <= len(body.ids) <= 4:
        raise HTTPException(400, "Vergelijk 1 tot 4 auto's")
    model = ensure_model(session)
    profile = get_profile(session, body.profile_id) if body.profile_id else None
    postcode = (profile.home_postcode if profile else None) or get_settings().home_postcode
    out = []
    for lid in body.ids:
        listing = get_listing(session, lid)
        vehicle = get_vehicle(session, listing)
        distance = _distance(session, listing, body.profile_id)
        issues = issues_for(listing, vehicle)

        def resale(years, kmpy, _l=listing):
            return model.project_value(_l, years, kmpy) if model else None

        tco = tco_compute(listing, vehicle, TcoInput(km_per_year=body.km_per_year), postcode, resale)
        c = card(listing, vehicle, distance,
                 composite(listing.score_components or {}, profile.weights if profile else None, distance))
        c.update({
            "vehicle": vehicle_to_dict(vehicle),
            "issues": [m.to_dict() for m in issues],
            "tco": tco,
            "ev": ev_mod.info(listing, vehicle),
        })
        out.append(c)
    return {"items": out}


class ImportIn(BaseModel):
    url: str | None = None
    kenteken: str | None = None


@router.post("/import")
def import_listing(body: ImportIn, session: Session = DB):
    """Add a single advert by URL (supported sites) so it gets scored and can be watched."""
    if not body.url:
        raise HTTPException(400, "Geef een advertentie-URL op")
    adapter = adapter_for_url(body.url)
    if adapter is None:
        raise HTTPException(400, "Alleen AutoScout24- en Marktplaats-links worden ondersteund")
    try:
        raw = adapter.detail(body.url)
    except Exception as exc:
        raise HTTPException(502, f"Ophalen mislukt: {exc}") from exc
    if raw is None:
        raise HTTPException(422, "Kon de advertentie niet lezen (parser niet geverifieerd voor deze pagina)")
    listing, _ = upsert(session, raw)
    refresh(session, [listing.id])
    return {"id": listing.id}


@router.get("/kenteken/{plate}")
def kenteken_lookup(plate: str, refresh_data: bool = False, session: Session = DB):
    import re

    from app.normalize.kenteken import format_plate, normalize

    compact = re.sub(r"[^A-Za-z0-9]", "", plate).upper()
    if compact.startswith("DEMO"):
        compact = "DM" + compact[4:]
    if compact.startswith("DM") and len(compact) == 8 and session.get(Vehicle, compact):
        norm = compact  # demo plate
    else:
        norm = normalize(compact)
    if norm is None:
        raise HTTPException(400, "Geen geldig Nederlands kenteken")
    vehicle = enrich(session, norm, force=refresh_data)
    listings = list(session.scalars(select(Listing).where(Listing.kenteken == norm).order_by(Listing.first_seen_at)))
    history = []
    for x in listings:
        prices = list(session.scalars(select(PriceHistory).where(PriceHistory.listing_id == x.id).order_by(PriceHistory.observed_at)))
        history.append({**card(x, vehicle), "price_history": [{"date": p.observed_at, "price": p.price_eur} for p in prices]})
    issues = []
    if listings:
        issues = [m.to_dict() for m in issues_for(listings[-1], vehicle)]
    return {
        "kenteken": format_plate(norm) if not norm.startswith("DM") else f"DEMO-{norm[2:]}",
        "vehicle": vehicle_to_dict(vehicle),
        "available": vehicle is not None,
        "offline": vehicle is None,
        "listings": history,
        "issues": issues,
    }
