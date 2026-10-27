"""Profiles, saved searches, watchlist (kanban), feed and alerts."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.alerts import ntfy
from app.api.deps import DB, get_listing, get_profile, get_vehicle
from app.api.serialize import card, scored_card
from app.config import get_settings
from app.feed import build_feed
from app.models import AlertSent, Listing, Profile, SavedSearch, WatchlistItem
from app.search import SearchFilters, SearchRequest, run_search
from app.util import utcnow

router = APIRouter(prefix="/api", tags=["personal"])

WATCH_STATUSES = ["interessant", "gebeld", "bezichtiging", "proefrit", "bod", "gekocht", "afgevallen"]


# -- profiles -----------------------------------------------------------------------------------
class ProfileIn(BaseModel):
    name: str | None = None
    home_postcode: str | None = None
    ntfy_topic: str | None = None
    weights: dict[str, float] | None = None


@router.get("/profiles")
def list_profiles(session: Session = DB):
    return [
        {"id": p.id, "name": p.name, "home_postcode": p.home_postcode, "ntfy_topic": p.ntfy_topic,
         "weights": p.weights or {}, "learned_weights": p.learned_weights or {}}
        for p in session.scalars(select(Profile).order_by(Profile.id))
    ]


@router.put("/profiles/{profile_id}")
def update_profile(profile_id: int, body: ProfileIn, session: Session = DB):
    p = get_profile(session, profile_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(p, key, value)
    return {"ok": True}


@router.post("/profiles/{profile_id}/test-push")
def test_push(profile_id: int, session: Session = DB):
    p = get_profile(session, profile_id)
    topic = p.ntfy_topic or get_settings().ntfy_topic
    if not topic:
        raise HTTPException(400, "Geen ntfy-topic ingesteld (profiel of NTFY_TOPIC)")
    ok = ntfy.publish(ntfy.build_payload(topic=topic, title="Autozoeker testmelding",
                                         message=f"Hoi {p.name}, pushmeldingen werken. 🚗", tags=["car", "white_check_mark"]))
    if not ok:
        raise HTTPException(502, "Versturen naar ntfy mislukt (server bereikbaar? topic juist?)")
    return {"ok": True}


# -- saved searches -------------------------------------------------------------------------------
class SavedSearchIn(BaseModel):
    profile_id: int
    name: str
    filters: SearchFilters = Field(default_factory=SearchFilters)
    weights: dict[str, float] = Field(default_factory=dict)
    alert_mode: Literal["instant", "daily", "off"] = "instant"
    min_match: int = Field(60, ge=0, le=100)
    price_drop_eur: int = 250
    price_drop_pct: float = 2.0


def _saved_dict(session: Session, s: SavedSearch) -> dict:
    new_7d = session.scalar(select(func.count()).select_from(AlertSent).where(
        AlertSent.saved_search_id == s.id, AlertSent.kind == "new",
    )) or 0
    return {
        "id": s.id, "profile_id": s.profile_id, "name": s.name, "filters": s.filters, "weights": s.weights,
        "alert_mode": s.alert_mode, "min_match": s.min_match, "price_drop_eur": s.price_drop_eur,
        "price_drop_pct": s.price_drop_pct, "created_at": s.created_at, "last_run_at": s.last_run_at,
        "alerts_total": new_7d,
    }


@router.get("/saved-searches")
def list_saved(profile_id: int | None = None, session: Session = DB):
    q = select(SavedSearch).order_by(SavedSearch.created_at.desc())
    if profile_id:
        q = q.where(SavedSearch.profile_id == profile_id)
    out = []
    for s in session.scalars(q):
        d = _saved_dict(session, s)
        scored = run_search(session, SearchRequest(filters=SearchFilters(**(s.filters or {})), weights=s.weights or {},
                                                   profile_id=s.profile_id))
        d["current_matches"] = sum(1 for x in scored if x.match >= s.min_match)
        d["total_results"] = len(scored)
        d["top"] = [scored_card(x) for x in scored[:3]]
        out.append(d)
    return out


@router.post("/saved-searches")
def create_saved(body: SavedSearchIn, session: Session = DB):
    get_profile(session, body.profile_id)
    s = SavedSearch(**body.model_dump(exclude={"filters"}), filters=body.filters.model_dump(exclude_defaults=True))
    s.last_run_at = utcnow()  # only alert on cars that appear from now on
    session.add(s)
    session.flush()
    return _saved_dict(session, s)


@router.put("/saved-searches/{search_id}")
def update_saved(search_id: int, body: SavedSearchIn, session: Session = DB):
    s = session.get(SavedSearch, search_id)
    if s is None:
        raise HTTPException(404, "Zoekopdracht niet gevonden")
    for key, value in body.model_dump(exclude={"filters"}).items():
        setattr(s, key, value)
    s.filters = body.filters.model_dump(exclude_defaults=True)
    return _saved_dict(session, s)


@router.delete("/saved-searches/{search_id}")
def delete_saved(search_id: int, session: Session = DB):
    s = session.get(SavedSearch, search_id)
    if s:
        session.delete(s)
    return {"ok": True}


# -- watchlist ------------------------------------------------------------------------------------
class WatchIn(BaseModel):
    listing_id: int
    profile_id: int | None = None
    status: str = "interessant"
    notes: str = ""


class WatchUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None
    checklist_state: dict | None = None


@router.get("/watchlist")
def list_watchlist(session: Session = DB):
    out = []
    for w in session.scalars(select(WatchlistItem).order_by(WatchlistItem.updated_at.desc())):
        listing = get_listing(session, w.listing_id)
        c = card(listing, get_vehicle(session, listing))
        c["watch"] = {"id": w.id, "status": w.status, "notes": w.notes, "price_at_add": w.price_at_add,
                      "added_at": w.added_at, "updated_at": w.updated_at, "checklist_state": w.checklist_state or {},
                      "added_by": w.added_by}
        out.append(c)
    return {"statuses": WATCH_STATUSES, "items": out}


@router.post("/watchlist")
def add_watch(body: WatchIn, session: Session = DB):
    listing = get_listing(session, body.listing_id)
    existing = session.scalar(select(WatchlistItem).where(WatchlistItem.listing_id == listing.id))
    if existing:
        return {"id": existing.id}
    w = WatchlistItem(listing_id=listing.id, added_by=body.profile_id, status=body.status, notes=body.notes,
                      price_at_add=listing.price_eur)
    session.add(w)
    session.flush()
    return {"id": w.id}


@router.put("/watchlist/{watch_id}")
def update_watch(watch_id: int, body: WatchUpdate, session: Session = DB):
    w = session.get(WatchlistItem, watch_id)
    if w is None:
        raise HTTPException(404, "Niet gevonden")
    if body.status is not None:
        if body.status not in WATCH_STATUSES:
            raise HTTPException(400, f"Status moet een van {WATCH_STATUSES} zijn")
        w.status = body.status
    if body.notes is not None:
        w.notes = body.notes
    if body.checklist_state is not None:
        w.checklist_state = body.checklist_state
    w.updated_at = utcnow()
    return {"ok": True}


@router.delete("/watchlist/{watch_id}")
def delete_watch(watch_id: int, session: Session = DB):
    w = session.get(WatchlistItem, watch_id)
    if w:
        session.delete(w)
    return {"ok": True}


# -- feed & alerts --------------------------------------------------------------------------------
@router.get("/feed")
def feed(profile_id: int, days: int = 7, session: Session = DB):
    items = build_feed(session, profile_id, days=days)
    watched = {w.listing_id for w in session.scalars(select(WatchlistItem))}
    return {
        "items": [
            scored_card(e["scored"], {"reasons": e["reasons"], "feed_score": e["feed_score"],
                                      "on_watchlist": e["scored"].listing.id in watched})
            for e in items
        ]
    }


@router.get("/alerts")
def list_alerts(profile_id: int, limit: int = 100, session: Session = DB):
    rows = session.execute(
        select(AlertSent, Listing).join(Listing, Listing.id == AlertSent.listing_id)
        .where(AlertSent.profile_id == profile_id).order_by(AlertSent.created_at.desc()).limit(limit)
    ).all()
    searches = {s.id: s.name for s in session.scalars(select(SavedSearch))}
    unseen = session.scalar(select(func.count()).select_from(AlertSent).where(
        AlertSent.profile_id == profile_id, AlertSent.seen.is_(False))) or 0
    return {
        "unseen": unseen,
        "items": [
            {"id": a.id, "kind": a.kind, "created_at": a.created_at, "delivery": a.delivery, "seen": a.seen,
             "match": a.match_score, "price_eur": a.price_eur, "message": a.message,
             "search": searches.get(a.saved_search_id), "listing": card(x)}
            for a, x in rows
        ],
    }


@router.post("/alerts/seen")
def mark_alerts_seen(profile_id: int, session: Session = DB):
    for a in session.scalars(select(AlertSent).where(AlertSent.profile_id == profile_id, AlertSent.seen.is_(False))):
        a.seen = True
    return {"ok": True}
