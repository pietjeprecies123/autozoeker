"""Turn a source-specific RawListing into canonical Listing fields."""

from __future__ import annotations

import hashlib
import re

from app.normalize import kenteken as kenteken_mod
from app.normalize.fields import (
    extract_battery_kwh,
    extract_engine_cc,
    extract_options,
    extract_power_kw,
    norm_body,
    norm_colour,
    norm_fuel,
    norm_transmission,
)
from app.normalize.taxonomy import match_vehicle
from app.sources.base import RawListing
from app.util import negated


def normalize_raw(raw: RawListing) -> dict:
    title = raw.title or " ".join(x for x in (raw.make_raw, raw.model_raw, raw.trim) if x)
    text = " ".join(x for x in (title, raw.trim or "") if x)
    year = raw.year or (raw.first_registration.year if raw.first_registration else None)

    match = match_vehicle(raw.make_raw, raw.model_raw, title, year)
    fuel = norm_fuel(raw.fuel_raw, text) or (match.fuel_hint if match else None)
    body = norm_body(raw.body_raw, text) or (match.body_hint if match else None)
    plate = kenteken_mod.normalize(raw.kenteken) or kenteken_mod.extract(raw.description)

    options = sorted(set(extract_options(title, raw.description, " ".join(raw.options_raw))))

    fields = {
        "source": raw.source,
        "source_id": raw.source_id,
        "url": raw.url,
        "title": title[:512],
        "make": match.make if match else None,
        "model": match.model if match else None,
        "generation": match.generation if match else None,
        "trim": (raw.trim or "")[:256] or None,
        "make_raw": raw.make_raw,
        "model_raw": raw.model_raw,
        "kenteken": plate,
        "year": year,
        "first_registration": raw.first_registration,
        "mileage_km": raw.mileage_km,
        "price_eur": raw.price_eur,
        "price_type": raw.price_type,
        "fuel": fuel,
        "transmission": norm_transmission(raw.transmission_raw, text if not raw.transmission_raw else ""),
        "body": body,
        "power_kw": raw.power_kw or extract_power_kw(text),
        "engine_cc": raw.engine_cc or extract_engine_cc(text),
        "battery_kwh": raw.battery_kwh or (extract_battery_kwh(text) if fuel in ("elektrisch", "plugin_hybride") else None),
        "doors": raw.doors,
        "seats": raw.seats,
        "colour": norm_colour(raw.colour_raw),
        "options": options,
        "seller_type": raw.seller_type,
        "seller_name": raw.seller_name,
        # private ads often say "onderhouden bij BOVAG-garage"; only a dealer can be a BOVAG member
        "seller_bovag": bool(raw.seller_bovag) or (raw.seller_type == "dealer" and _mentions_bovag(raw.description)),
        "warranty_months": raw.warranty_months,
        "postcode": (raw.postcode or "")[:4] or None,
        "city": raw.city,
        "lat": raw.lat,
        "lon": raw.lon,
        "image_urls": raw.image_urls[:12],
        "description": raw.description or "",
        "extra": raw.extra,
        "is_demo": raw.is_demo,
    }
    fields["fingerprint"] = fingerprint(fields)
    return fields


def _mentions_bovag(text: str | None) -> bool:
    t = (text or "").lower()
    return any(not negated(t, m.start()) for m in re.finditer(r"bovag", t))


def fingerprint(f: dict) -> str | None:
    """Coarse identity for cross-site dedupe when no kenteken is known.

    Same make/model/year/fuel, km rounded to 1.000 and PC2 region. Price is deliberately excluded
    (sites differ by a few hundred euro); the pipeline additionally requires prices within 7%.
    """
    if not (f.get("make") and f.get("model") and f.get("year") and f.get("mileage_km")):
        return None
    region = (f.get("postcode") or "")[:2]
    key = "|".join(
        str(x)
        for x in (f["make"], f["model"], f["year"], f.get("fuel") or "", round(f["mileage_km"] / 1000), region)
    )
    return hashlib.sha1(key.encode()).hexdigest()[:16]
