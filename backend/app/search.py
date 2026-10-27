"""Search: structured filters → scored, sorted, de-duplicated listings. Shared by the API and alerts."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from pydantic import BaseModel, Field
from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.enrich.geo import geocode, haversine_km, road_km
from app.models import Listing, Profile, Vehicle
from app.scoring.components import composite


class SearchFilters(BaseModel):
    q: str | None = None
    makes: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)  # "make/model"
    generations: list[str] = Field(default_factory=list)
    fuels: list[str] = Field(default_factory=list)
    bodies: list[str] = Field(default_factory=list)
    transmissions: list[str] = Field(default_factory=list)
    price_min: int | None = None
    price_max: int | None = None
    km_min: int | None = None
    km_max: int | None = None
    year_min: int | None = None
    year_max: int | None = None
    kw_min: int | None = None
    kw_max: int | None = None
    seats_min: int | None = None
    colours: list[str] = Field(default_factory=list)
    options: list[str] = Field(default_factory=list)
    towing_min: int | None = None
    range_min: int | None = None
    max_distance_km: int | None = None
    seller_types: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    bovag_only: bool = False
    warranty_only: bool = False
    hide_import: bool = False
    hide_nap_issues: bool = False
    hide_open_recall: bool = False
    hide_high_flags: bool = False
    hide_battery_lease: bool = False
    min_deal_pct: int | None = None
    include_removed: bool = False
    include_demo: bool | None = None  # None → follow DEMO_MODE


class SearchRequest(BaseModel):
    filters: SearchFilters = Field(default_factory=SearchFilters)
    sort: str = "best"  # best | deal | price_asc | price_desc | km | newest | distance | year
    weights: dict[str, float] = Field(default_factory=dict)
    page: int = 1
    page_size: int = 30
    profile_id: int | None = None
    collapse_duplicates: bool = True


@dataclass
class Scored:
    listing: Listing
    vehicle: Vehicle | None
    distance_km: float | None
    match: int
    duplicates: list[Listing]


def home_location(session: Session, profile: Profile | None) -> tuple[float, float] | None:
    postcode = (profile.home_postcode if profile and profile.home_postcode else None) or get_settings().home_postcode
    loc = geocode(session, postcode)
    return (loc[0], loc[1]) if loc else None


def build_query(f: SearchFilters):
    settings = get_settings()
    q = select(Listing, Vehicle).outerjoin(Vehicle, Vehicle.kenteken == Listing.kenteken)
    q = q.options(selectinload(Listing.prices))
    if not f.include_removed:
        q = q.where(Listing.status == "active")
    include_demo = settings.demo_mode if f.include_demo is None else f.include_demo
    if not include_demo:
        q = q.where(Listing.is_demo.is_(False))
    if f.q:
        for word in f.q.split():
            q = q.where(Listing.title.ilike(f"%{word}%"))
    if f.makes or f.models:
        conds = []
        if f.makes:
            conds.append(Listing.make.in_(f.makes))
        for mm in f.models:
            make, _, model = mm.partition("/")
            conds.append((Listing.make == make) & (Listing.model == model))
        q = q.where(or_(*conds))
    if f.generations:
        q = q.where(Listing.generation.in_(f.generations))
    if f.fuels:
        q = q.where(Listing.fuel.in_(f.fuels))
    if f.bodies:
        q = q.where(Listing.body.in_(f.bodies))
    if f.transmissions:
        q = q.where(Listing.transmission.in_(f.transmissions))
    if f.colours:
        q = q.where(Listing.colour.in_(f.colours))
    if f.sources:
        q = q.where(Listing.source.in_(f.sources))
    if f.seller_types:
        q = q.where(Listing.seller_type.in_(f.seller_types))
    for col, lo, hi in (
        (Listing.price_eur, f.price_min, f.price_max),
        (Listing.mileage_km, f.km_min, f.km_max),
        (Listing.year, f.year_min, f.year_max),
        (Listing.power_kw, f.kw_min, f.kw_max),
    ):
        if lo is not None:
            q = q.where(col >= lo)
        if hi is not None:
            q = q.where(col <= hi)
    if f.seats_min:
        q = q.where(or_(Listing.seats >= f.seats_min, Vehicle.seats >= f.seats_min))
    if f.bovag_only:
        q = q.where(Listing.seller_bovag.is_(True))
    if f.warranty_only:
        q = q.where(Listing.warranty_months > 0)
    if f.towing_min:
        q = q.where(Vehicle.towing_braked >= f.towing_min)
    if f.range_min:
        q = q.where(Vehicle.range_km >= f.range_min)
    if f.hide_import:
        q = q.where(or_(Vehicle.is_import.is_(None), Vehicle.is_import.is_(False)))
    if f.hide_nap_issues:
        q = q.where(or_(Vehicle.odometer_judgement.is_(None), ~Vehicle.odometer_judgement.ilike("%onlogisch%")))
    if f.hide_open_recall:
        q = q.where(or_(Vehicle.open_recall.is_(None), Vehicle.open_recall.is_(False)))
    for opt in f.options:
        q = q.where(cast(Listing.options, String).like(f'%"{opt}"%'))
    if f.min_deal_pct is not None:
        q = q.where(Listing.deal_score >= f.min_deal_pct / 100)
    return q


def score_rows(session: Session, rows, f: SearchFilters, weights: dict, home, collapse: bool = True) -> list[Scored]:
    groups: dict[int, list[tuple[Listing, Vehicle | None]]] = {}
    order: list[int] = []
    for listing, vehicle in rows:
        if f.hide_high_flags and any(fl.get("severity") == "high" for fl in (listing.red_flags or [])):
            continue
        if f.hide_battery_lease and any(fl.get("code") == "battery_lease" for fl in (listing.red_flags or [])):
            continue
        key = (listing.group_id or listing.id) if collapse else listing.id
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((listing, vehicle))

    out: list[Scored] = []
    for key in order:
        members = sorted(groups[key], key=lambda lv: lv[0].price_eur or 10**9)
        listing, vehicle = members[0]
        distance = None
        if home and listing.lat is not None and listing.lon is not None:
            distance = round(road_km(haversine_km(home[0], home[1], listing.lat, listing.lon)), 1)
        if f.max_distance_km is not None and (distance is None or distance > f.max_distance_km):
            continue
        match = composite(listing.score_components or {}, weights, distance)
        out.append(Scored(listing, vehicle, distance, match, [m[0] for m in members[1:]]))
    return out


SORTS = {
    "best": lambda s: -s.match,
    "deal": lambda s: -(s.listing.deal_score if s.listing.deal_score is not None else -9),
    "price_asc": lambda s: s.listing.price_eur or 10**9,
    "price_desc": lambda s: -(s.listing.price_eur or 0),
    "km": lambda s: s.listing.mileage_km if s.listing.mileage_km is not None else 10**9,
    "newest": lambda s: -s.listing.first_seen_at.timestamp(),
    "distance": lambda s: s.distance_km if s.distance_km is not None else 10**6,
    "year": lambda s: -(s.listing.year or 0),
}


def run_search(session: Session, req: SearchRequest, listing_ids: list[int] | None = None) -> list[Scored]:
    profile = session.get(Profile, req.profile_id) if req.profile_id else None
    weights = dict(profile.weights or {}) if profile else {}
    if profile and profile.learned_weights:
        for k, v in profile.learned_weights.items():
            weights[k] = 0.5 * weights.get(k, v) + 0.5 * v
    weights.update(req.weights or {})
    q = build_query(req.filters)
    if listing_ids is not None:
        q = q.where(Listing.id.in_(listing_ids))
    rows = session.execute(q).all()
    home = home_location(session, profile)
    scored = score_rows(session, rows, req.filters, weights, home, req.collapse_duplicates)
    scored.sort(key=SORTS.get(req.sort, SORTS["best"]))
    return scored


def pareto_frontier(points: list[tuple[int, float, float]]) -> set[int]:
    """Ids of points not dominated on (price, km): no other car is both cheaper and has fewer km."""
    frontier: set[int] = set()
    best_km = math.inf
    for pid, _price, km in sorted(points, key=lambda p: (p[1], p[2])):
        if km < best_km:
            frontier.add(pid)
            best_km = km
    return frontier


def summarize(scored: list[Scored]) -> dict:
    prices = [s.listing.price_eur for s in scored if s.listing.price_eur]
    kms = [s.listing.mileage_km for s in scored if s.listing.mileage_km is not None]
    deals = [s.listing.deal_score for s in scored if s.listing.deal_score is not None]
    facets: dict[str, dict[str, int]] = {"fuel": {}, "body": {}, "make": {}, "transmission": {}, "source": {}}
    for s in scored:
        for key, value in (("fuel", s.listing.fuel), ("body", s.listing.body), ("make", s.listing.make),
                           ("transmission", s.listing.transmission), ("source", s.listing.source)):
            if value:
                facets[key][value] = facets[key].get(value, 0) + 1
    return {
        "count": len(scored),
        "median_price": int(statistics.median(prices)) if prices else None,
        "median_km": int(statistics.median(kms)) if kms else None,
        "price_min": min(prices) if prices else None,
        "price_max": max(prices) if prices else None,
        "share_under_market": round(sum(1 for d in deals if d > 0.03) / len(deals), 3) if deals else None,
        "facets": facets,
    }


def pareto_points(scored: list[Scored], limit: int = 800) -> list[dict]:
    pts = [(s.listing.id, s.listing.price_eur, s.listing.mileage_km) for s in scored
           if s.listing.price_eur and s.listing.mileage_km is not None]
    frontier = pareto_frontier(pts)
    by_id = {s.listing.id: s for s in scored}
    out = []
    # always include frontier + best matches first, then the rest up to the limit
    ordered = sorted(pts, key=lambda p: (p[0] not in frontier, -by_id[p[0]].match))
    for pid, price, km in ordered[:limit]:
        s = by_id[pid]
        out.append({
            "id": pid,
            "price": price,
            "km": km,
            "year": s.listing.year,
            "title": s.listing.title,
            "match": s.match,
            "deal_score": s.listing.deal_score,
            "frontier": pid in frontier,
        })
    return out
