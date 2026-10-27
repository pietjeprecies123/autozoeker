"""Total cost of ownership per month and per km (Dutch defaults, all user-overridable)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models import Listing, Vehicle
from app.tco.mrb import estimate_quarter, province_for_postcode
from app.util import age_in_months

# Defaults; prices as of mid/late 2026 (CBS pump prices June–July 2026, typical energy contracts).
ENERGY_DEFAULTS = {
    "euro95_per_l": 2.30,
    "diesel_per_l": 2.35,
    "lpg_per_l": 0.95,
    "kwh_home": 0.28,
    "kwh_public": 0.55,
    "public_share": 0.3,
    "peildatum": "CBS-gemiddelden juni/juli 2026; aan te passen onder 'Energieprijzen aanpassen'",
}

# Rough monthly maintenance (incl. tyres) by fuel; EVs need less.
MAINTENANCE_BASE = {"elektrisch": 35, "hybride": 50, "plugin_hybride": 55, "benzine": 55, "diesel": 65, "lpg": 65}
INSURANCE_DEFAULT = 65  # €/month all-risk-ish for an average car; user should fill in a real quote


class TcoInput(BaseModel):
    km_per_year: int = Field(13000, ge=0, le=100_000)
    years: int = Field(3, ge=1, le=15)
    insurance_month: float | None = None
    maintenance_month: float | None = None
    mrb_quarter_override: float | None = None
    province: str | None = None
    euro95_per_l: float | None = None
    diesel_per_l: float | None = None
    lpg_per_l: float | None = None
    kwh_home: float | None = None
    kwh_public: float | None = None
    public_share: float | None = None
    future_value: int | None = None  # override projected resale value


def _default_consumption(listing: Listing) -> tuple[float | None, float | None]:
    """(l/100km, kWh/100km) when RDW has no figures."""
    kw = listing.power_kw or 80
    if listing.fuel == "elektrisch":
        return None, 17.0 + max(0, (kw - 150)) / 100
    if listing.fuel == "plugin_hybride":
        return 2.0, 16.0
    if listing.fuel == "hybride":
        return 4.6, None
    if listing.fuel == "diesel":
        return 5.0 + kw / 300, None
    return 5.6 + kw / 250, None


def compute(listing: Listing, vehicle: Vehicle | None, inp: TcoInput, home_postcode: str | None,
            resale_fn=None) -> dict:
    e = {k: getattr(inp, k) if getattr(inp, k, None) is not None else v for k, v in ENERGY_DEFAULTS.items()
         if k != "peildatum"}
    l_100, kwh_100 = (None, None)
    if vehicle and (vehicle.consumption_l_100km or vehicle.consumption_kwh_100km):
        l_100, kwh_100 = vehicle.consumption_l_100km, vehicle.consumption_kwh_100km
    d_l, d_kwh = _default_consumption(listing)
    l_100 = l_100 or d_l
    kwh_100 = kwh_100 or d_kwh
    # WLTP is optimistic in practice: +12% for combustion, +15% for EV (Dutch winters)
    real_l = l_100 * 1.12 if l_100 else None
    real_kwh = kwh_100 * 1.15 if kwh_100 else None

    km_month = inp.km_per_year / 12
    fuel_cost = 0.0
    if listing.fuel == "elektrisch" and real_kwh:
        price = e["kwh_home"] * (1 - e["public_share"]) + e["kwh_public"] * e["public_share"]
        fuel_cost = km_month * real_kwh / 100 * price
    elif listing.fuel == "plugin_hybride":
        # assume 45% electric km for a typical PHEV owner who charges at home
        price_kwh = e["kwh_home"] * (1 - e["public_share"]) + e["kwh_public"] * e["public_share"]
        fuel_cost = km_month * 0.45 * (real_kwh or 16) / 100 * price_kwh + km_month * 0.55 * 6.5 / 100 * e["euro95_per_l"]
    elif real_l:
        per_l = {"diesel": e["diesel_per_l"], "lpg": e["lpg_per_l"]}.get(listing.fuel or "", e["euro95_per_l"])
        if listing.fuel == "lpg":
            real_l *= 1.25  # LPG consumption in litres is ~25% higher
        fuel_cost = km_month * real_l / 100 * per_l

    weight = None
    if vehicle and vehicle.mass_ready:
        weight = vehicle.mass_ready
    elif vehicle and vehicle.mass_empty:
        weight = vehicle.mass_empty + 100
    province = inp.province or province_for_postcode(home_postcode)
    mrb = estimate_quarter(weight, listing.fuel, province, listing.first_registration)
    mrb_month = (inp.mrb_quarter_override / 3) if inp.mrb_quarter_override is not None else (mrb["month"] or 0)

    age = (age_in_months(listing.first_registration, listing.year) or 0) / 12
    maint = inp.maintenance_month
    if maint is None:
        maint = MAINTENANCE_BASE.get(listing.fuel or "", 55) * (1 + max(0, age - 5) * 0.06)
        if (listing.mileage_km or 0) > 150_000:
            maint *= 1.15
    insurance = inp.insurance_month if inp.insurance_month is not None else INSURANCE_DEFAULT

    price = listing.price_eur or 0
    future = inp.future_value
    if future is None and resale_fn is not None:
        future = resale_fn(inp.years, inp.km_per_year)
    if future is None:
        future = int(price * (0.88 ** inp.years))
    depreciation_month = max(0, price - future) / (inp.years * 12)

    total = fuel_cost + mrb_month + maint + insurance + depreciation_month
    return {
        "inputs": {**inp.model_dump(), **{k: e[k] for k in e}},
        "consumption": {
            "wltp_l_100km": l_100,
            "wltp_kwh_100km": kwh_100,
            "real_l_100km": round(real_l, 1) if real_l else None,
            "real_kwh_100km": round(real_kwh, 1) if real_kwh else None,
            "source": "RDW" if vehicle and (vehicle.consumption_l_100km or vehicle.consumption_kwh_100km) else "schatting",
        },
        "mrb": {**mrb, "province": province, "month_used": round(mrb_month, 2)},
        "monthly": {
            "brandstof_energie": round(fuel_cost, 2),
            "wegenbelasting": round(mrb_month, 2),
            "onderhoud_banden": round(maint, 2),
            "verzekering": round(insurance, 2),
            "afschrijving": round(depreciation_month, 2),
            "totaal": round(total, 2),
        },
        "per_km": round(total * 12 / inp.km_per_year, 3) if inp.km_per_year else None,
        "resale_value": future,
        "years": inp.years,
        "notes": [
            "Wegenbelasting is een schatting; controleer het exacte bedrag bij de Belastingdienst.",
            "Verzekering is een standaardwaarde; vul je eigen premie in voor een betere vergelijking.",
            f"Energieprijzen: {ENERGY_DEFAULTS['peildatum']}.",
        ],
    }
