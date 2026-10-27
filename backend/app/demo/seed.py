"""Load the DEMO dataset, and simulate market activity on each crawl cycle in demo mode."""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.demo.generator import DemoCar, generate
from app.enrich.geo import pc2_centroid
from app.ingest.pipeline import IngestResult, upsert
from app.models import Listing, PriceHistory, Vehicle
from app.normalize import normalize_raw
from app.util import utcnow

log = logging.getLogger(__name__)


def _place(car: DemoCar, rng: random.Random) -> None:
    loc = pc2_centroid(car.raw.postcode)
    if loc:
        car.raw.lat = round(loc[0] + rng.uniform(-0.06, 0.06), 5)
        car.raw.lon = round(loc[1] + rng.uniform(-0.09, 0.09), 5)


def _store(session: Session, car: DemoCar, rng: random.Random, now: datetime | None = None) -> tuple[Listing, str]:
    _place(car, rng)
    first_price = car.price_history[0][1]
    final_price = car.raw.price_eur
    car.raw.price_eur = first_price
    listing, outcome = upsert(session, car.raw, now=now or car.first_seen_at, enrich=False)
    for when, price in car.price_history[1:]:
        listing.price_eur = price
        session.add(PriceHistory(listing_id=listing.id, price_eur=price, observed_at=when))
    listing.price_eur = final_price
    car.raw.price_eur = final_price
    if car.removed_at:
        listing.status = "removed"
        listing.removed_at = car.removed_at
        listing.last_seen_at = car.removed_at
    else:
        listing.last_seen_at = now or utcnow()
    if session.get(Vehicle, car.vehicle["kenteken"]) is None:
        session.add(Vehicle(**car.vehicle, fetched_at=utcnow()))
    return listing, outcome


def demo_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Listing).where(Listing.is_demo.is_(True))) or 0


def seed_demo(session: Session, n: int = 5000, seed: int = 42, now: datetime | None = None) -> int:
    """Insert the demo dataset once (bulk path: every car is new and single-source). Returns count."""
    if demo_count(session) > 0:
        return 0
    now = now or utcnow()
    rng = random.Random(seed)
    cars = generate(n, seed=seed, now=now)
    with session.no_autoflush:
        for i, car in enumerate(cars, 1):
            _place(car, rng)
            fields = normalize_raw(car.raw)
            fields["kenteken"] = car.raw.kenteken
            listing = Listing(**fields, first_seen_at=car.first_seen_at, status="active")
            listing.prices = [PriceHistory(price_eur=p, observed_at=t) for t, p in car.price_history]
            listing.price_eur = car.price_history[-1][1]
            if car.removed_at:
                listing.status = "removed"
                listing.removed_at = car.removed_at
                listing.last_seen_at = car.removed_at
            else:
                listing.last_seen_at = now
            session.add(listing)
            session.add(Vehicle(**car.vehicle, fetched_at=now))
            if i % 1000 == 0:
                session.flush()
    session.flush()
    session.execute(update(Listing).where(Listing.group_id.is_(None)).values(group_id=Listing.id))
    log.info("Seeded %d demo listings", n)
    return n


def demo_tick(session: Session, now: datetime | None = None, new_count: int | None = None) -> IngestResult:
    """Simulate a crawl cycle: a few new cars, some price drops, some cars sold."""
    now = now or utcnow()
    rng = random.Random(int(now.timestamp()))
    result = IngestResult()
    offset = (session.scalar(select(func.max(Listing.id))) or 0) + 100000
    count = new_count if new_count is not None else rng.randint(3, 9)
    for car in generate(count, seed=rng.randint(1, 10**9), now=now, history_days=0, id_offset=offset):
        car.price_history = [(now, car.raw.price_eur)]
        car.removed_at = None
        listing, outcome = _store(session, car, rng, now=now)
        listing.first_seen_at = now
        result.new.append(listing.id)

    active = session.scalars(
        select(Listing).where(Listing.is_demo.is_(True), Listing.status == "active", Listing.first_seen_at < now - timedelta(days=3))
        .order_by(func.random()).limit(12)
    ).all()
    for listing in active[:8]:
        if listing.price_eur:
            new_price = int(round(listing.price_eur * rng.uniform(0.94, 0.985) / 250) * 250 - 5)
            if new_price < listing.price_eur:
                listing.price_eur = new_price
                session.add(PriceHistory(listing_id=listing.id, price_eur=new_price, observed_at=now))
                result.price_changed.append(listing.id)
    for listing in active[8:]:
        listing.status = "removed"
        listing.removed_at = now
        result.removed.append(listing.id)
    session.flush()
    return result
