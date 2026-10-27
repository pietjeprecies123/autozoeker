"""EV-specific info: battery warranty left, realistic range, heat pump, battery lease."""

from __future__ import annotations

from datetime import date

from app.knowledge.service import files_for
from app.models import Listing, Vehicle
from app.util import age_in_months

# Fallback when the knowledge base has no model-specific battery warranty.
# Most manufacturers give 8 years / 160.000 km with a minimum state of health of ~70%.
DEFAULT_WARRANTY = {"years": 8, "km": 160000, "min_soh_pct": 70, "note": "Gangbare fabrieksgarantie; controleer de voorwaarden per merk."}


def info(listing: Listing, vehicle: Vehicle | None) -> dict | None:
    if listing.fuel not in ("elektrisch", "plugin_hybride"):
        return None
    warranty = None
    for f in files_for(listing.make, listing.model):
        if f.get("battery_warranty"):
            warranty = dict(f["battery_warranty"])
            break
    is_default = warranty is None
    warranty = warranty or dict(DEFAULT_WARRANTY)

    reg: date | None = vehicle.first_admission if vehicle and vehicle.first_admission else listing.first_registration
    age_m = age_in_months(reg, listing.year)
    years_left = None
    km_left = None
    if age_m is not None and warranty.get("years"):
        years_left = round(max(0.0, warranty["years"] - age_m / 12), 1)
    if listing.mileage_km is not None and warranty.get("km"):
        km_left = max(0, warranty["km"] - listing.mileage_km)
    covered = bool(years_left and km_left)

    wltp = vehicle.range_km if vehicle and vehicle.range_km else None
    if wltp is None and listing.battery_kwh and listing.fuel == "elektrisch":
        kwh_100 = (vehicle.consumption_kwh_100km if vehicle and vehicle.consumption_kwh_100km else 17.0)
        wltp = int(listing.battery_kwh * 0.93 / kwh_100 * 100)
    heat_pump = "warmtepomp" in (listing.options or [])
    battery_lease = bool((listing.extra or {}).get("battery_lease")) or any(
        f.get("code") == "battery_lease" for f in (listing.red_flags or [])
    )
    real = None
    if wltp:
        winter = 0.72 if heat_pump else 0.62
        real = {"wltp": wltp, "zomer": int(wltp * 0.9), "winter": int(wltp * winter), "snelweg_130": int(wltp * 0.68)}
    return {
        "warranty": warranty,
        "warranty_is_default": is_default,
        "warranty_years_left": years_left,
        "warranty_km_left": km_left,
        "warranty_covered": covered,
        "range": real,
        "heat_pump": heat_pump,
        "battery_lease": battery_lease,
        "battery_kwh": listing.battery_kwh,
        "advice": [
            "Vraag een batterijtest (State of Health). Dealers kunnen uitlezen; onafhankelijk bijv. via Aviloo.",
            "Batterijgarantie geldt meestal alleen bij een SoH onder de drempel (vaak 70%) binnen de termijn.",
        ] + (["Huuraccu: de accu blijft van de leasemaatschappij; reken de maandelijkse huur mee of vraag naar uitkoop."]
             if battery_lease else []),
    }
