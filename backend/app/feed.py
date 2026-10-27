"""'Nieuw voor jou': recent listings ranked by saved-search match and similarity to cars you liked.

Feedback (thumbs up/down) also tunes the best-match weights per profile: with enough votes we fit a
logistic regression on the score components and blend its positive coefficients with the defaults.
"""

from __future__ import annotations

import math
from datetime import timedelta

import numpy as np
from sklearn.linear_model import LogisticRegression
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Feedback, Listing, Profile, SavedSearch, WatchlistItem
from app.search import SearchFilters, SearchRequest, run_search
from app.util import age_in_months, utcnow

COMPONENTS = ["deal", "km", "health", "issues", "seller"]


def learn_weights(session: Session, profile_id: int) -> dict:
    profile = session.get(Profile, profile_id)
    if profile is None:
        return {}
    rows = session.execute(
        select(Feedback.value, Listing.score_components).join(Listing, Listing.id == Feedback.listing_id)
        .where(Feedback.profile_id == profile_id)
    ).all()
    X = [[(comps or {}).get(c, 0.5) for c in COMPONENTS] for _, comps in rows]
    y = [1 if v > 0 else 0 for v, _ in rows]
    if len(rows) < 6 or len(set(y)) < 2:
        profile.learned_weights = {}
        return {}
    clf = LogisticRegression(C=1.0).fit(np.array(X), np.array(y))
    coefs = np.clip(clf.coef_[0], 0, None)
    if coefs.sum() <= 0:
        profile.learned_weights = {}
        return {}
    w = coefs / coefs.sum() * 0.95  # leave 5% for distance
    learned = {c: round(float(v), 3) for c, v in zip(COMPONENTS, w, strict=True)}
    learned["distance"] = 0.05
    profile.learned_weights = learned
    return learned


def _vector(x: Listing) -> np.ndarray:
    age = (age_in_months(x.first_registration, x.year) or 60) / 12
    return np.array([
        age / 3,
        (x.mileage_km or 100_000) / 40_000,
        math.log((x.price_eur or 10_000) + 1) * 2,
        (x.power_kw or 80) / 40,
    ])


def similarity(a: Listing, b: Listing) -> float:
    d = float(np.linalg.norm(_vector(a) - _vector(b)))
    s = math.exp(-d / 2)
    if a.make == b.make and a.model == b.model:
        s = s * 0.6 + 0.4
    elif a.body == b.body and a.fuel == b.fuel:
        s = s * 0.8 + 0.1
    else:
        s *= 0.6
    return max(0.0, min(1.0, s))


def build_feed(session: Session, profile_id: int, days: int = 7, limit: int = 60) -> list[dict]:
    since = utcnow() - timedelta(days=days)
    recent_ids = list(session.scalars(
        select(Listing.id).where(Listing.status == "active", Listing.first_seen_at >= since)
    ))
    if not recent_ids:
        return []
    disliked = set(session.scalars(select(Feedback.listing_id).where(Feedback.profile_id == profile_id, Feedback.value < 0)))
    liked_ids = set(session.scalars(select(Feedback.listing_id).where(Feedback.profile_id == profile_id, Feedback.value > 0)))
    liked_ids |= set(session.scalars(select(WatchlistItem.listing_id)))
    liked = list(session.scalars(select(Listing).where(Listing.id.in_(liked_ids)))) if liked_ids else []

    best: dict[int, dict] = {}
    searches = list(session.scalars(select(SavedSearch).where(SavedSearch.profile_id == profile_id)))
    for search in searches:
        req = SearchRequest(filters=SearchFilters(**(search.filters or {})), weights=search.weights or {},
                            profile_id=profile_id, page_size=1000)
        for s in run_search(session, req, listing_ids=recent_ids):
            entry = best.setdefault(s.listing.id, {"scored": s, "match": 0, "reasons": []})
            if s.match >= entry["match"]:
                entry["match"] = s.match
                entry["scored"] = s
            entry["reasons"].append(f"Past bij '{search.name}' ({s.match}%)")

    if liked:
        # similarity to liked/watched cars, for recent listings not already matched by a search
        generic = run_search(session, SearchRequest(profile_id=profile_id, page_size=5000), listing_ids=recent_ids)
        for s in generic:
            sims = [(similarity(s.listing, ref), ref) for ref in liked if ref.id != s.listing.id]
            if not sims:
                continue
            sim, ref = max(sims, key=lambda t: t[0])
            if sim < 0.55:
                continue
            entry = best.setdefault(s.listing.id, {"scored": s, "match": s.match, "reasons": []})
            entry["similarity"] = round(sim, 2)
            entry["reasons"].append(f"Lijkt op {ref.title} die je bewaarde of leuk vond")

    items = []
    for lid, entry in best.items():
        if lid in disliked:
            continue
        sim = entry.get("similarity", 0)
        score = entry["match"] * (0.75 if sim else 1.0) + sim * 25
        items.append({**entry, "feed_score": round(score, 1)})
    items.sort(key=lambda e: -e["feed_score"])
    return items[:limit]


def preload(session: Session, ids: list[int]) -> None:
    if ids:
        list(session.scalars(select(Listing).options(selectinload(Listing.prices)).where(Listing.id.in_(ids))))
