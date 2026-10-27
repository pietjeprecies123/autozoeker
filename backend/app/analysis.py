"""Recompute derived data for listings: market value, deal score, score components, red flags."""

from __future__ import annotations

import logging
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.knowledge import service as knowledge
from app.models import Listing, Vehicle
from app.scoring import redflags
from app.scoring.components import deal_component, health_component, km_component, seller_component
from app.util import utcnow
from app.valuation.model import ValuationModel, get_model_instance, hedonic_or_comparables, train

log = logging.getLogger(__name__)


def ensure_model(session: Session) -> ValuationModel:
    model = get_model_instance()
    if model is None:
        model = train(session)
    return model


def refresh(session: Session, ids: list[int] | None = None, retrain: bool = False) -> int:
    """Recompute valuation + scoring for the given listings (default: all active). Returns count."""
    model = train(session) if retrain else ensure_model(session)
    knowledge.load_ai_files(session)
    q = select(Listing).options(selectinload(Listing.prices))
    if ids is not None:
        if not ids:
            return 0
        q = q.where(Listing.id.in_(ids))
    else:
        q = q.where(Listing.status == "active")
    listings = list(session.scalars(q))
    if not listings:
        return 0

    valuations = model.predict_many(listings)
    # small-data fallback per make/model
    missing = [x for x in listings if x.id not in valuations]
    if missing:
        by_model: dict[tuple, list[Listing]] = defaultdict(list)
        for x in missing:
            by_model[(x.make, x.model)].append(x)
        for (make, mdl), group in by_model.items():
            if not make or not mdl:
                continue
            comps = list(session.scalars(select(Listing).where(Listing.make == make, Listing.model == mdl).limit(400)))
            for x in group:
                v = hedonic_or_comparables(x, comps)
                if v:
                    v.expected_km = model.expected_km(x)
                    valuations[x.id] = v

    plates = {x.kenteken for x in listings if x.kenteken}
    vehicles = {v.kenteken: v for v in session.scalars(select(Vehicle).where(Vehicle.kenteken.in_(plates)))} if plates else {}

    now = utcnow()
    ctx = redflags.context(session)
    with session.no_autoflush:
        _apply(listings, valuations, vehicles, ctx, session, now)
    session.flush()
    log.info("refreshed %d listings", len(listings))
    return len(listings)


def _apply(listings, valuations, vehicles, ctx, session, now) -> None:
    for x in listings:
        v = valuations.get(x.id)
        if v:
            x.predicted_price, x.predicted_low, x.predicted_high = v.predicted, v.low, v.high
            x.valuation_method, x.valuation_confidence = v.method, v.confidence
            x.km_effect_eur, x.expected_km = v.km_effect_eur, v.expected_km
            x.deal_score = round((v.predicted - x.price_eur) / v.predicted, 4) if x.price_eur and v.predicted else None
        else:
            x.predicted_price = x.predicted_low = x.predicted_high = None
            x.valuation_method = x.valuation_confidence = None
            x.deal_score = None
        vehicle = vehicles.get(x.kenteken) if x.kenteken else None
        km_score, km_ratio = km_component(x, x.expected_km)
        health, health_notes = health_component(x, vehicle)
        issue_score, issue_cost, issue_count = knowledge.risk(x, vehicle)
        flags = redflags.compute(session, x, vehicle, ctx)
        x.red_flags = flags
        x.score_components = {
            "deal": round(deal_component(x.deal_score), 3),
            "km": round(km_score, 3),
            "km_ratio": km_ratio,
            "health": round(health, 3),
            "health_notes": health_notes,
            "issues": round(issue_score, 3),
            "issue_cost": issue_cost,
            "issue_count": issue_count,
            "seller": round(seller_component(x), 3),
            "flag_penalty": round(redflags.penalty(flags), 3),
        }
        x.valued_at = now
