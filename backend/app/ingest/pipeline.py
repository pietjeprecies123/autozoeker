"""Ingest: RawListing → normalised, deduplicated, enriched Listing rows with price history."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enrich import geo
from app.enrich.rdw import enrich as rdw_enrich
from app.models import CrawlRun, Listing, PriceHistory
from app.normalize import normalize_raw
from app.sources.base import RawListing, SourceAdapter, SourceBlocked, SourceQuery
from app.util import utcnow

log = logging.getLogger(__name__)

# Fields that may legitimately change while an advert is online
MUTABLE = (
    "url", "title", "price_eur", "price_type", "mileage_km", "description", "image_urls", "options",
    "seller_name", "seller_bovag", "warranty_months", "extra",
)


@dataclass
class IngestResult:
    new: list[int] = field(default_factory=list)
    price_changed: list[int] = field(default_factory=list)
    back: list[int] = field(default_factory=list)
    removed: list[int] = field(default_factory=list)
    unchanged: int = 0
    errors: list[str] = field(default_factory=list)

    def merge(self, other: IngestResult) -> None:
        self.new += other.new
        self.price_changed += other.price_changed
        self.back += other.back
        self.removed += other.removed
        self.unchanged += other.unchanged
        self.errors += other.errors

    @property
    def touched(self) -> list[int]:
        return self.new + self.price_changed + self.back


def _assign_group(session: Session, listing: Listing) -> None:
    """Link the same car advertised on several sites (kenteken, else fingerprint + similar price)."""
    candidate = None
    if listing.kenteken:
        candidate = session.scalar(
            select(Listing).where(
                Listing.kenteken == listing.kenteken,
                Listing.id != listing.id,
                Listing.source != listing.source,
            ).order_by(Listing.id).limit(1)
        )
    if candidate is None and listing.fingerprint and listing.price_eur:
        for other in session.scalars(
            select(Listing).where(
                Listing.fingerprint == listing.fingerprint,
                Listing.id != listing.id,
                Listing.source != listing.source,
                Listing.status == "active",
            ).limit(5)
        ):
            if other.price_eur and abs(other.price_eur - listing.price_eur) <= 0.07 * listing.price_eur:
                candidate = other
                break
    listing.group_id = (candidate.group_id or candidate.id) if candidate else listing.id


def upsert(session: Session, raw: RawListing, now: datetime | None = None, enrich: bool = True) -> tuple[Listing, str]:
    """Insert or update one listing. Returns (listing, outcome) with outcome new|price|back|unchanged."""
    now = now or utcnow()
    fields = normalize_raw(raw)
    if raw.is_demo and raw.kenteken:
        fields["kenteken"] = raw.kenteken  # demo plates (DM000123) are deliberately not valid NL plates

    listing = session.scalar(
        select(Listing).where(Listing.source == raw.source, Listing.source_id == raw.source_id)
    )
    if listing is None:
        listing = Listing(**fields, first_seen_at=now, last_seen_at=now, status="active")
        if listing.lat is None and listing.postcode:
            loc = geo.geocode(session, listing.postcode)
            if loc:
                listing.lat, listing.lon = loc[0], loc[1]
        session.add(listing)
        session.flush()
        if listing.price_eur:
            session.add(PriceHistory(listing_id=listing.id, price_eur=listing.price_eur, observed_at=now))
        _assign_group(session, listing)
        outcome = "new"
    else:
        outcome = "unchanged"
        if listing.status != "active":
            listing.status = "active"
            listing.removed_at = None
            outcome = "back"
        old_price = listing.price_eur
        for key in MUTABLE:
            value = fields.get(key)
            if value not in (None, "", [], {}):
                setattr(listing, key, value)
        # identity fields: only fill gaps, never overwrite
        for key in ("kenteken", "make", "model", "generation", "first_registration", "year", "fuel",
                    "transmission", "body", "power_kw", "postcode", "lat", "lon"):
            if getattr(listing, key) is None and fields.get(key) is not None:
                setattr(listing, key, fields[key])
        listing.last_seen_at = now
        if listing.price_eur and listing.price_eur != old_price:
            session.add(PriceHistory(listing_id=listing.id, price_eur=listing.price_eur, observed_at=now))
            if outcome == "unchanged":
                outcome = "price"
    if enrich and listing.kenteken and not raw.is_demo:
        rdw_enrich(session, listing.kenteken)
    return listing, outcome


def ingest_many(session: Session, raws, now: datetime | None = None, enrich: bool = True) -> IngestResult:
    result = IngestResult()
    for raw in raws:
        try:
            listing, outcome = upsert(session, raw, now=now, enrich=enrich)
        except Exception as exc:  # one bad advert must not kill the run
            log.exception("ingest failed for %s/%s", raw.source, raw.source_id)
            result.errors.append(f"{raw.source}/{raw.source_id}: {exc}")
            continue
        if outcome == "new":
            result.new.append(listing.id)
        elif outcome == "price":
            result.price_changed.append(listing.id)
        elif outcome == "back":
            result.back.append(listing.id)
        else:
            result.unchanged += 1
    session.flush()
    return result


def crawl(session: Session, adapter: SourceAdapter, query: SourceQuery) -> IngestResult:
    """Run one adapter query, record a CrawlRun for the health page."""
    run = CrawlRun(source=adapter.name, query_key=query.key(), started_at=utcnow(), status="running")
    session.add(run)
    session.flush()
    result = IngestResult()
    fetched = 0
    try:
        batch: list[RawListing] = []
        for raw in adapter.search(query):
            fetched += 1
            batch.append(raw)
            if len(batch) >= 50:
                result.merge(ingest_many(session, batch))
                batch = []
        if batch:
            result.merge(ingest_many(session, batch))
        run.status = "partial" if result.errors else "ok"
    except SourceBlocked as exc:
        run.status = "blocked"
        run.error = str(exc)
    except Exception as exc:
        log.exception("crawl %s failed", adapter.name)
        run.status = "error"
        run.error = f"{type(exc).__name__}: {exc}"
    run.finished_at = utcnow()
    run.n_fetched = fetched
    run.n_new = len(result.new)
    run.n_updated = len(result.price_changed) + len(result.back)
    run.n_errors = len(result.errors)
    if result.errors and not run.error:
        run.error = "\n".join(result.errors[:5])
    return result


def mark_stale(session: Session, sources: list[str], max_age_hours: int = 72) -> list[int]:
    """Mark listings not seen for a while as removed (likely sold). Returns their ids."""
    cutoff = utcnow() - timedelta(hours=max_age_hours)
    stale = session.scalars(
        select(Listing).where(
            Listing.status == "active",
            Listing.source.in_(sources),
            Listing.last_seen_at < cutoff,
        )
    ).all()
    now = utcnow()
    for listing in stale:
        listing.status = "removed"
        listing.removed_at = now
    return [x.id for x in stale]


def queries_for_crawl(session: Session) -> list[SourceQuery]:
    """What to crawl: every saved search plus the make/model of every watched car.

    Distinct make/model pairs are crawled broadly (no price filter) so the valuation model gets
    enough comparables; saved-search filters are applied afterwards in the database.
    """
    from app.models import SavedSearch, WatchlistItem

    pairs: set[tuple[str | None, str | None]] = set()
    texts: set[str] = set()
    for search in session.scalars(select(SavedSearch)):
        f = search.filters or {}
        makes = f.get("makes") or []
        models = f.get("models") or []
        if models:
            for mm in models:
                make, _, model = str(mm).partition("/")
                pairs.add((make, model or None))
        elif makes:
            for make in makes:
                pairs.add((make, None))
        elif f.get("q"):
            texts.add(f["q"])
    for item in session.scalars(select(WatchlistItem)):
        listing = session.get(Listing, item.listing_id)
        if listing and listing.make:
            pairs.add((listing.make, listing.model))
    queries = [SourceQuery(make=mk, model=md) for mk, md in sorted(pairs, key=lambda p: (p[0] or "", p[1] or ""))]
    queries += [SourceQuery(text=t) for t in sorted(texts)]
    return queries


def listings_by_ids(session: Session, ids: list[int]) -> list[Listing]:
    if not ids:
        return []
    return list(session.scalars(select(Listing).where(Listing.id.in_(ids))))

