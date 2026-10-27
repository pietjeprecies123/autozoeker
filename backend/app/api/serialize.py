"""Listing → JSON-ready dicts for the UI."""

from __future__ import annotations

from app.models import Listing, Vehicle
from app.normalize.fields import BODY_LABELS, FUEL_LABELS, OPTION_LABELS
from app.normalize.kenteken import format_plate
from app.normalize.taxonomy import generation_name, get_model, load_taxonomy
from app.search import Scored
from app.util import utcnow

SOURCE_LABELS = {"autoscout24": "AutoScout24", "marktplaats": "Marktplaats", "gaspedaal": "Gaspedaal",
                 "demo": "DEMO", "manual": "Handmatig"}


def make_name(make: str | None) -> str | None:
    if not make:
        return None
    mk = load_taxonomy().get(make)
    return mk.name if mk else make


def model_name(make: str | None, model: str | None) -> str | None:
    md = get_model(make, model)
    return md.name if md else model


def plate_display(plate: str | None) -> str | None:
    if not plate:
        return None
    if plate.startswith("DM") and len(plate) == 8:
        return f"DEMO-{plate[2:]}"
    return format_plate(plate)


def card(listing: Listing, vehicle: Vehicle | None = None, distance_km: float | None = None,
         match: int | None = None, duplicates: list[Listing] | None = None, extra: dict | None = None) -> dict:
    prices = listing.prices or []
    first_price = prices[0].price_eur if prices else listing.price_eur
    comps = listing.score_components or {}
    out = {
        "id": listing.id,
        "title": listing.title,
        "make": listing.make,
        "model": listing.model,
        "make_name": make_name(listing.make),
        "model_name": model_name(listing.make, listing.model),
        "generation": listing.generation,
        "generation_name": generation_name(listing.make, listing.model, listing.generation),
        "trim": listing.trim,
        "kenteken": plate_display(listing.kenteken),
        "year": listing.year,
        "first_registration": listing.first_registration,
        "mileage_km": listing.mileage_km,
        "price_eur": listing.price_eur,
        "price_type": listing.price_type,
        "first_price_eur": first_price,
        "price_drops": max(0, len(prices) - 1),
        "fuel": listing.fuel,
        "fuel_label": FUEL_LABELS.get(listing.fuel or "", listing.fuel),
        "transmission": listing.transmission,
        "body": listing.body,
        "body_label": BODY_LABELS.get(listing.body or "", listing.body),
        "power_kw": listing.power_kw,
        "power_pk": int(round(listing.power_kw / 0.7355)) if listing.power_kw else None,
        "battery_kwh": listing.battery_kwh,
        "colour": listing.colour,
        "seller_type": listing.seller_type,
        "seller_name": listing.seller_name,
        "seller_bovag": listing.seller_bovag,
        "warranty_months": listing.warranty_months,
        "postcode": listing.postcode,
        "city": listing.city,
        "lat": listing.lat,
        "lon": listing.lon,
        "distance_km": distance_km,
        "image_url": (listing.image_urls or [None])[0],
        "source": listing.source,
        "source_label": SOURCE_LABELS.get(listing.source, listing.source),
        "url": listing.url,
        "is_demo": listing.is_demo,
        "status": listing.status,
        "first_seen_at": listing.first_seen_at,
        "removed_at": listing.removed_at,
        "days_online": (utcnow() - listing.first_seen_at).days if listing.first_seen_at else None,
        "predicted_price": listing.predicted_price,
        "predicted_low": listing.predicted_low,
        "predicted_high": listing.predicted_high,
        "valuation_confidence": listing.valuation_confidence,
        "valuation_method": listing.valuation_method,
        "deal_score": listing.deal_score,
        "deal_eur": (listing.predicted_price - listing.price_eur) if listing.predicted_price and listing.price_eur else None,
        "km_effect_eur": listing.km_effect_eur,
        "expected_km": listing.expected_km,
        "match": match,
        "components": {k: comps.get(k) for k in ("deal", "km", "health", "issues", "seller")},
        "km_ratio": comps.get("km_ratio"),
        "issue_count": comps.get("issue_count", 0),
        "issue_cost": comps.get("issue_cost", 0),
        "health_notes": comps.get("health_notes", []),
        "red_flags": listing.red_flags or [],
        "options": listing.options or [],
        "option_labels": [OPTION_LABELS.get(o, o) for o in (listing.options or [])],
        "duplicates": [
            {"id": d.id, "source": d.source, "source_label": SOURCE_LABELS.get(d.source, d.source),
             "url": d.url, "price_eur": d.price_eur}
            for d in (duplicates or [])
        ],
    }
    if vehicle is not None:
        out["rdw"] = {
            "found": vehicle.found,
            "apk_expiry": vehicle.apk_expiry,
            "odometer_judgement": vehicle.odometer_judgement,
            "open_recall": vehicle.open_recall,
            "is_import": vehicle.is_import,
            "taxi": vehicle.taxi,
            "towing_braked": vehicle.towing_braked,
            "range_km": vehicle.range_km,
        }
    else:
        out["rdw"] = None
    if extra:
        out.update(extra)
    return out


def scored_card(s: Scored, extra: dict | None = None) -> dict:
    return card(s.listing, s.vehicle, s.distance_km, s.match, s.duplicates, extra)
