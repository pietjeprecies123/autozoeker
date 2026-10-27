"""Turn crawl results into alerts: new matches for saved searches, price drops, back-on-market, sold."""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.alerts import ntfy
from app.api.serialize import make_name, model_name
from app.config import get_settings
from app.ingest.pipeline import IngestResult
from app.models import AlertSent, Listing, PriceHistory, Profile, SavedSearch, WatchlistItem
from app.search import SearchFilters, SearchRequest, run_search
from app.util import euro, km, utcnow

log = logging.getLogger(__name__)

Publisher = Callable[[dict], bool]

KIND_TAGS = {"new": ["car", "sparkles"], "price_drop": ["car", "chart_with_downwards_trend"],
             "back": ["car", "leftwards_arrow_with_hook"], "sold": ["car", "checkered_flag"]}
KIND_LABEL = {"new": "Nieuw", "price_drop": "Prijsdaling", "back": "Weer te koop", "sold": "Verkocht/offline"}


def _topic(profile: Profile) -> str:
    return profile.ntfy_topic or get_settings().ntfy_topic


def _previous_price(session: Session, listing: Listing) -> int | None:
    prices = list(session.scalars(
        select(PriceHistory.price_eur).where(PriceHistory.listing_id == listing.id).order_by(PriceHistory.observed_at.desc()).limit(2)
    ))
    return prices[1] if len(prices) > 1 else None


def _message(listing: Listing, kind: str, match: int | None, search_name: str | None, prev: int | None) -> tuple[str, str]:
    name = f"{make_name(listing.make) or ''} {model_name(listing.make, listing.model) or ''}".strip() or listing.title
    title = f"{KIND_LABEL[kind]}: {name} {listing.year or ''} – {euro(listing.price_eur)}"
    lines = [f"**{listing.title}**", f"{listing.year or '?'} · {km(listing.mileage_km)} · {listing.fuel or ''}"]
    if kind == "price_drop" and prev:
        lines.append(f"Prijs {euro(prev)} → **{euro(listing.price_eur)}** (−{euro(prev - (listing.price_eur or 0))})")
    if listing.deal_score is not None and listing.predicted_price:
        pct = round(listing.deal_score * 100)
        lines.append(f"Marktwaarde ≈ {euro(listing.predicted_price)} ({'+' if pct >= 0 else ''}{pct}% voordeel)")
    if match is not None:
        lines.append(f"Match {match}%" + (f" met '{search_name}'" if search_name else ""))
    flags = [f["title"] for f in (listing.red_flags or []) if f.get("severity") in ("high", "medium")]
    if flags:
        lines.append("⚠️ " + ", ".join(flags[:3]))
    if listing.is_demo:
        lines.append("_(DEMO-data)_")
    return title, "\n".join(lines)


def _payload(profile: Profile, listing: Listing, kind: str, match: int | None, search_name: str | None, prev: int | None) -> dict:
    settings = get_settings()
    title, message = _message(listing, kind, match, search_name, prev)
    app_link = f"{settings.app_url.rstrip('/')}/auto/{listing.id}"
    actions = [{"action": "view", "label": "In Autozoeker", "url": app_link}]
    if listing.url and not listing.is_demo:
        actions.insert(0, {"action": "view", "label": "Advertentie", "url": listing.url})
    image = (listing.image_urls or [None])[0]
    return ntfy.build_payload(
        topic=_topic(profile), title=title, message=message, click=app_link, attach=image,
        tags=KIND_TAGS.get(kind), priority=4 if (match or 0) >= 85 or kind == "price_drop" else 3, actions=actions,
    )


def _record(session: Session, profile: Profile, listing: Listing, kind: str, match: int | None,
            search: SavedSearch | None, publisher: Publisher, prev: int | None = None) -> AlertSent | None:
    if search is None:
        # NULL saved_search_id is not covered by the unique constraint (NULLs are distinct), check by hand
        exists = session.scalar(select(AlertSent.id).where(
            AlertSent.profile_id == profile.id, AlertSent.saved_search_id.is_(None), AlertSent.listing_id == listing.id,
            AlertSent.kind == kind, AlertSent.price_eur == listing.price_eur,
        ))
        if exists:
            return None
    alert = AlertSent(
        profile_id=profile.id, saved_search_id=search.id if search else None, listing_id=listing.id, kind=kind,
        price_eur=listing.price_eur, match_score=match,
    )
    title, message = _message(listing, kind, match, search.name if search else None, prev)
    alert.message = f"{title}\n{message}"
    try:
        with session.begin_nested():
            session.add(alert)
            session.flush()
    except IntegrityError:
        return None  # already alerted for this listing/kind/price
    mode = search.alert_mode if search else "instant"
    if mode == "daily":
        alert.delivery = "digest"
    elif _topic(profile):
        ok = publisher(_payload(profile, listing, kind, match, search.name if search else None, prev))
        alert.delivery = "sent" if ok else "failed"
        alert.delivered_at = utcnow() if ok else None
    else:
        alert.delivery = "skipped"  # no ntfy topic configured: in-app only
    return alert


def process(session: Session, result: IngestResult, publisher: Publisher = ntfy.publish) -> list[AlertSent]:
    """Evaluate new/changed listings against every saved search and the watchlist."""
    created: list[AlertSent] = []
    touched = set(result.touched)
    kinds = {i: "new" for i in result.new} | {i: "price_drop" for i in result.price_changed} | {i: "back" for i in result.back}
    profiles = {p.id: p for p in session.scalars(select(Profile))}

    if touched:
        for search in session.scalars(select(SavedSearch).where(SavedSearch.alert_mode != "off")):
            profile = profiles.get(search.profile_id)
            if not profile:
                continue
            req = SearchRequest(filters=SearchFilters(**(search.filters or {})), weights=search.weights or {},
                                profile_id=profile.id, page_size=1000)
            for s in run_search(session, req, listing_ids=list(touched)):
                kind = kinds.get(s.listing.id, "new")
                if s.match < search.min_match:
                    continue
                prev = None
                if kind == "price_drop":
                    prev = _previous_price(session, s.listing)
                    if not prev or not s.listing.price_eur or s.listing.price_eur >= prev:
                        continue
                    drop = prev - s.listing.price_eur
                    if drop < search.price_drop_eur and drop / prev * 100 < search.price_drop_pct:
                        continue
                alert = _record(session, profile, s.listing, kind, s.match, search, publisher, prev)
                if alert:
                    created.append(alert)
            search.last_run_at = utcnow()

    # watchlist: every price drop and every car that goes offline
    watch = {w.listing_id: w for w in session.scalars(select(WatchlistItem))}
    for lid in set(result.price_changed) | set(result.removed):
        w = watch.get(lid)
        if not w or w.status in ("gekocht", "afgevallen"):
            continue
        listing = session.get(Listing, lid)
        if listing is None:
            continue
        targets = [profiles[w.added_by]] if w.added_by in profiles else list(profiles.values())
        kind = "sold" if lid in result.removed else "price_drop"
        prev = _previous_price(session, listing) if kind == "price_drop" else None
        if kind == "price_drop" and (not prev or (listing.price_eur or 0) >= prev):
            continue
        for profile in targets:
            alert = _record(session, profile, listing, kind, None, None, publisher, prev)
            if alert:
                created.append(alert)
    session.flush()
    return created


def send_digests(session: Session, publisher: Publisher = ntfy.publish) -> int:
    """Send one bundled push per profile for alerts queued as 'digest'."""
    sent = 0
    settings = get_settings()
    for profile in session.scalars(select(Profile)):
        pending = list(session.scalars(
            select(AlertSent).where(AlertSent.profile_id == profile.id, AlertSent.delivery == "digest")
            .order_by(AlertSent.match_score.desc().nullslast()).limit(50)
        ))
        if not pending:
            continue
        topic = _topic(profile)
        lines = []
        for a in pending[:10]:
            first = a.message.split("\n", 1)[0]
            lines.append(f"- {first}" + (f" ({a.match_score}%)" if a.match_score else ""))
        if len(pending) > 10:
            lines.append(f"… en nog {len(pending) - 10}")
        ok = False
        if topic:
            ok = publisher(ntfy.build_payload(
                topic=topic, title=f"Autozoeker: {len(pending)} nieuwe matches", message="\n".join(lines),
                click=f"{settings.app_url.rstrip('/')}/voor-jou", tags=["car", "newspaper"],
            ))
        now = utcnow()
        for a in pending:
            a.delivery = "sent" if ok else ("skipped" if not topic else "failed")
            a.delivered_at = now if ok else None
        sent += 1 if ok else 0
    session.flush()
    return sent
