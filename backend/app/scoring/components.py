"""Best-match score: a weighted blend of per-car components, each scaled 0..1.

Components that do not depend on the viewer are computed at ingest and stored on the listing;
distance depends on the viewer's home and is added at query time.
"""

from __future__ import annotations

import re

from app.models import Listing, Vehicle
from app.util import age_in_months, clamp, today

DEFAULT_WEIGHTS: dict[str, float] = {
    "deal": 0.35,
    "km": 0.15,
    "health": 0.20,
    "issues": 0.15,
    "seller": 0.10,
    "distance": 0.05,
}
COMPONENT_LABELS = {
    "deal": "Prijs t.o.v. marktwaarde",
    "km": "Kilometerstand voor de leeftijd",
    "health": "RDW-historie (NAP, APK, terugroepacties)",
    "issues": "Bekende aandachtspunten",
    "seller": "Verkoper (dealer, BOVAG, garantie)",
    "distance": "Afstand",
}


def deal_component(deal_score: float | None) -> float:
    if deal_score is None:
        return 0.5
    # -15% (overpriced) → 0, at market → 0.5, 15%+ under market → 1
    return clamp((deal_score + 0.15) / 0.30)


def km_component(listing: Listing, expected_km: int | None) -> tuple[float, float | None]:
    if listing.mileage_km is None:
        return 0.5, None
    if not expected_km:
        age = age_in_months(listing.first_registration, listing.year) or 12
        expected_km = int(13000 * max(age, 6) / 12)
    ratio = listing.mileage_km / max(expected_km, 3000)
    score = clamp(1.25 - 0.5 * ratio)
    if listing.mileage_km > 200_000:
        score *= clamp(1 - (listing.mileage_km - 200_000) / 200_000)
    return score, round(ratio, 2)


def health_component(listing: Listing, vehicle: Vehicle | None) -> tuple[float, list[str]]:
    notes: list[str] = []
    if vehicle is None or not vehicle.found:
        return (0.6, ["Geen RDW-gegevens (kenteken onbekend)"]) if vehicle is None else (0.3, ["Kenteken niet gevonden bij RDW"])
    score = 1.0
    nap = (vehicle.odometer_judgement or "").lower()
    if "onlogisch" in nap:
        score -= 0.6
        notes.append("NAP: onlogisch")
    elif "geen oordeel" in nap or not nap:
        score -= 0.1
        notes.append("NAP: geen oordeel")
    if vehicle.open_recall:
        score -= 0.25
        notes.append("Openstaande terugroepactie")
    if vehicle.apk_expiry:
        days = (vehicle.apk_expiry - today()).days
        if days < 0:
            score -= 0.2
            notes.append("APK verlopen")
        elif days < 60:
            score -= 0.1
            notes.append("APK verloopt binnen 2 maanden")
    if vehicle.taxi:
        score -= 0.3
        notes.append("Ex-taxi")
    if vehicle.is_import:
        score -= 0.1
        notes.append("Import (km-historie buitenland niet in NAP)")
    if vehicle.export:
        score -= 0.4
        notes.append("Export-indicator")
    return clamp(score), notes


_HISTORY_WORDS = re.compile(r"onderhoudsboekje|facturen|dealer onderhouden|onderhoudshistorie|1e eigenaar|eerste eigenaar", re.I)


def seller_component(listing: Listing) -> float:
    if listing.seller_type == "dealer":
        score = 0.6
        if listing.seller_bovag:
            score += 0.2
        if listing.warranty_months and listing.warranty_months >= 6:
            score += 0.15
        elif listing.warranty_months:
            score += 0.07
    else:
        score = 0.45
    if _HISTORY_WORDS.search(listing.description or ""):
        score += 0.08
    return clamp(score)


def distance_component(distance_km: float | None) -> float:
    if distance_km is None:
        return 0.6
    return clamp(1 - distance_km / 150)


def normalize_weights(weights: dict | None) -> dict[str, float]:
    w = dict(DEFAULT_WEIGHTS)
    for k, v in (weights or {}).items():
        if k in w and v is not None:
            w[k] = max(0.0, float(v))
    total = sum(w.values()) or 1.0
    return {k: v / total for k, v in w.items()}


def composite(components: dict, weights: dict | None = None, distance_km: float | None = None) -> int:
    w = normalize_weights(weights)
    values = {
        "deal": components.get("deal", 0.5),
        "km": components.get("km", 0.5),
        "health": components.get("health", 0.6),
        "issues": components.get("issues", 0.75),
        "seller": components.get("seller", 0.5),
        "distance": distance_component(distance_km),
    }
    score = sum(values[k] * w[k] for k in w)
    penalty = components.get("flag_penalty", 0.0)
    return int(round(clamp(score - penalty) * 100))
