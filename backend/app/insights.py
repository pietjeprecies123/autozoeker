"""Market insights per make/model: prices, depreciation, supply and time-to-sale."""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from datetime import timedelta

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import Listing
from app.util import age_in_months, price_drops, utcnow


def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    return float(np.percentile(values, q))


def model_insights(session: Session, make: str, model: str | None = None, fuel: str | None = None, days: int = 120) -> dict:
    settings = get_settings()
    since = utcnow() - timedelta(days=days)
    q = select(Listing).options(selectinload(Listing.prices)).where(Listing.make == make, Listing.last_seen_at >= since)
    if model:
        q = q.where(Listing.model == model)
    if fuel:
        q = q.where(Listing.fuel == fuel)
    if not settings.demo_mode:
        q = q.where(Listing.is_demo.is_(False))
    rows = list(session.scalars(q))
    active = [x for x in rows if x.status == "active" and x.price_eur]
    sold = [x for x in rows if x.status == "removed" and x.removed_at and x.price_eur]

    prices = [x.price_eur for x in active]
    hist = []
    if prices:
        lo, hi = min(prices), max(prices)
        step = max(500, int(math.ceil((hi - lo) / 12 / 500.0)) * 500)
        start = (lo // step) * step
        counts = Counter((p - start) // step for p in prices)
        for i in range(int((hi - start) // step) + 1):
            hist.append({"from": int(start + i * step), "to": int(start + (i + 1) * step), "count": counts.get(i, 0)})

    by_year: dict[int, list[int]] = defaultdict(list)
    for x in active:
        if x.year:
            by_year[x.year].append(x.price_eur)
    per_year = [
        {"year": y, "median": int(statistics.median(v)), "p25": int(_pct(v, 25)), "p75": int(_pct(v, 75)), "count": len(v)}
        for y, v in sorted(by_year.items())
    ]

    scatter = [{"id": x.id, "km": x.mileage_km, "price": x.price_eur, "year": x.year, "deal": x.deal_score}
               for x in active if x.mileage_km is not None][:800]
    trend = None
    pts = [(x.mileage_km, x.price_eur) for x in active if x.mileage_km is not None and x.price_eur]
    if len(pts) >= 8:
        kms = np.array([p[0] for p in pts], dtype=float)
        logp = np.log(np.array([p[1] for p in pts], dtype=float))
        slope, intercept = np.polyfit(kms, logp, 1)
        xs = np.linspace(kms.min(), kms.max(), 20)
        trend = {
            "line": [{"km": int(k), "price": int(math.exp(intercept + slope * k))} for k in xs],
            "per_10k_km_pct": round((math.exp(slope * 10000) - 1) * 100, 2),
        }

    # depreciation: median price by age in whole years
    by_age: dict[int, list[int]] = defaultdict(list)
    for x in active:
        a = age_in_months(x.first_registration, x.year)
        if a is not None:
            by_age[a // 12].append(x.price_eur)
    depreciation = [{"age": a, "median": int(statistics.median(v)), "count": len(v)} for a, v in sorted(by_age.items())]
    yearly_loss = None
    if len(depreciation) >= 3:
        ages = np.array([d["age"] for d in depreciation], dtype=float)
        meds = np.log(np.array([d["median"] for d in depreciation], dtype=float))
        w = np.array([d["count"] for d in depreciation], dtype=float)
        slope, _ = np.polyfit(ages, meds, 1, w=np.sqrt(w))
        yearly_loss = round((1 - math.exp(slope)) * 100, 1)

    # supply per week (reconstructed from first_seen / removed_at)
    supply = []
    now = utcnow()
    for wk in range(days // 7, -1, -1):
        t = now - timedelta(days=7 * wk)
        n = sum(1 for x in rows if x.first_seen_at <= t and (x.removed_at is None or x.removed_at > t))
        supply.append({"week": t.date().isoformat(), "count": n})

    days_to_sale = [(x.removed_at - x.first_seen_at).days for x in sold]
    with_drop = sum(1 for x in active if price_drops(x.prices))
    deals = sorted(
        [x for x in active if x.deal_score is not None and x.valuation_confidence != "low"
         and not any(f.get("severity") == "high" for f in (x.red_flags or []))],
        key=lambda x: -x.deal_score,
    )[:8]
    fuels = Counter(x.fuel for x in active if x.fuel)
    return {
        "make": make,
        "model": model,
        "active": len(active),
        "sold_recently": len(sold),
        "median_price": int(statistics.median(prices)) if prices else None,
        "median_km": int(statistics.median([x.mileage_km for x in active if x.mileage_km is not None])) if active else None,
        "histogram": hist,
        "per_year": per_year,
        "scatter": scatter,
        "trend": trend,
        "depreciation": depreciation,
        "yearly_value_loss_pct": yearly_loss,
        "supply": supply,
        "median_days_to_sale": int(statistics.median(days_to_sale)) if days_to_sale else None,
        "share_price_drop": round(with_drop / len(active), 3) if active else None,
        "fuels": dict(fuels),
        "deal_ids": [x.id for x in deals],
    }


def best_deals(session: Session, limit: int = 24) -> list[Listing]:
    settings = get_settings()
    q = (select(Listing).options(selectinload(Listing.prices))
         .where(Listing.status == "active", Listing.deal_score.is_not(None), Listing.valuation_confidence.in_(["high", "medium"]))
         .order_by(Listing.deal_score.desc()).limit(limit * 4))
    if not settings.demo_mode:
        q = q.where(Listing.is_demo.is_(False))
    out = []
    for x in session.scalars(q):
        if any(f.get("severity") == "high" for f in (x.red_flags or [])):
            continue
        out.append(x)
        if len(out) >= limit:
            break
    return out
