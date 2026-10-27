"""Synthetic DEMO listings with plausible Dutch prices, mileage, sellers and RDW-like vehicle data.

All generated cars carry is_demo=True and a demo plate of the form 'DM123456' (8 characters, so it
can never collide with a real Dutch kenteken). The UI labels them as DEMO everywhere.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from app.demo.catalog import (
    CATALOG,
    COLOUR_WEIGHTS,
    COLOURS,
    DEALER_NAMES,
    OPTION_POOL,
    PC2_WEIGHTS,
    PRIVATE_NAMES,
)
from app.normalize.fields import OPTION_LABELS
from app.normalize.taxonomy import get_model, load_taxonomy
from app.sources.base import RawListing

ANNUAL_KM = {"benzine": 12000, "diesel": 22000, "elektrisch": 15000, "hybride": 14500, "plugin_hybride": 16000, "lpg": 20000}
SEGMENT_MASS = {"A": 900, "B": 1120, "C": 1320, "D": 1500, "E": 1700, "SUV-B": 1250, "SUV-C": 1480, "SUV-D": 1750,
                "SUV-E": 2150, "MPV": 1500, "LUX": 2050, "SPORT": 1100}
SEGMENT_TOW = {"A": 0, "B": 900, "C": 1300, "D": 1600, "E": 1900, "SUV-B": 1200, "SUV-C": 1600, "SUV-D": 2000,
               "SUV-E": 2700, "MPV": 1500, "LUX": 2000, "SPORT": 0}
SEGMENT_KWH = {"A": 14.5, "B": 15.5, "C": 16.5, "D": 16.0, "E": 18.0, "SUV-B": 16.5, "SUV-C": 18.0, "SUV-D": 19.5,
               "SUV-E": 23.0, "MPV": 19.0, "LUX": 20.0, "SPORT": 17.0}
SEGMENT_L = {"A": 4.6, "B": 5.1, "C": 5.6, "D": 6.0, "E": 6.6, "SUV-B": 5.6, "SUV-C": 6.2, "SUV-D": 6.9,
             "SUV-E": 8.0, "MPV": 6.3, "LUX": 8.5, "SPORT": 6.8}
TAXI_PRONE = {"prius", "model-3", "octavia", "ioniq", "niro", "c-klasse", "e-klasse", "model-s", "corolla", "superb"}

DEMO_RECALLS = [
    ("DEMO-R001", "Software-update batterijmanagementsysteem", "Mogelijk verlies van aandrijving door softwarefout in het batterijmanagement."),
    ("DEMO-R002", "Controle bevestiging airbagmodule", "De airbag aan bestuurderszijde kan onjuist zijn gemonteerd."),
    ("DEMO-R003", "Vervanging brandstofleiding", "Brandstofleiding kan lekken door slijtage tegen een beugel."),
    ("DEMO-R004", "Inspectie bovenste draagarm voorwielophanging", "Draagarm kan scheuren bij extreme belasting."),
]
DEMO_APK_DEFECTS = [
    ("AC1", "Band(en) profieldiepte onvoldoende"),
    ("RA2", "Remschijf/-trommel versleten"),
    ("205", "Lamp verlichting defect"),
    ("497", "Ruitenwisser(s) werkt niet naar behoren"),
    ("K04", "Uitlaatsysteem lekt"),
]


@dataclass
class DemoCar:
    raw: RawListing
    first_seen_at: datetime
    removed_at: datetime | None
    price_history: list[tuple[datetime, int]]
    vehicle: dict = field(default_factory=dict)


def _weighted(rng: random.Random, items: list, weights: list[float]):
    return rng.choices(items, weights=weights, k=1)[0]


def _first_apk(reg: date, fuel: str) -> date:
    years = 3 if fuel in ("diesel", "lpg") else 4
    return date(reg.year + years, reg.month, min(reg.day, 28))


def _next_apk(reg: date, fuel: str, now: date, rng: random.Random) -> date:
    due = _first_apk(reg, fuel)
    while due < now - timedelta(days=30):
        age = due.year - reg.year
        step = 1 if (fuel in ("diesel", "lpg") or age >= 8) else 2
        due = date(due.year + step, due.month, due.day)
    # cars are often keured early; jitter a bit
    return due + timedelta(days=rng.randint(-40, 40))


def _value(new_price: float, age_years: float, fuel: str, retention: float, km: int, expected_km: float) -> float:
    first = 0.24 if fuel == "elektrisch" else 0.17
    annual = (0.135 if fuel == "elektrisch" else 0.105) / retention
    if age_years <= 1:
        v = new_price * (1 - first * age_years)
    else:
        v = new_price * (1 - first) * (1 - annual) ** (age_years - 1)
    # mileage relative to normal for the age: ~2.2% value per 10.000 km
    v *= math.exp(-0.022 * (km - expected_km) / 10000)
    return v


def _round_price(p: float, dealer: bool, rng: random.Random) -> int:
    if dealer:
        return int(max(1495, round(p / 250) * 250 - rng.choice([0, 5, 50, 55])))
    return int(max(950, round(p / 100) * 100))


def _postcode(rng: random.Random) -> str:
    pc2 = _weighted(rng, list(PC2_WEIGHTS.keys()), list(PC2_WEIGHTS.values()))
    return f"{pc2}{rng.randint(0, 99):02d}"


def _description(rng: random.Random, car: dict, options: list[str], dealer: bool, flags: list[str]) -> str:
    parts = []
    if dealer:
        parts.append(rng.choice([
            "Nette auto, dealer onderhouden.", "Volledig onderhoudshistorie aanwezig.",
            "Goed onderhouden occasion, rijdt uitstekend.", "Auto verkeert in nieuwstaat.",
        ]))
        parts.append(rng.choice(["NAP aanwezig.", "Met NAP-tellerrapport.", "Kilometerstand logisch (NAP)."]))
        if car["bovag"]:
            parts.append("BOVAG garantie, BOVAG-certificaat en 40-puntencheck.")
        if car["warranty"]:
            parts.append(f"Inclusief {car['warranty']} maanden garantie.")
        parts.append(rng.choice(["Inruil mogelijk.", "Financiering mogelijk.", "Inruil en financiering bespreekbaar."]))
    else:
        parts.append(rng.choice([
            "Wegens aanschaf nieuwe auto te koop.", "Zeer nette auto, altijd binnen gestald.",
            "Ik verkoop mijn trouwe auto.", "Moet weg ivm verhuizing.",
        ]))
        if rng.random() < 0.6:
            parts.append(rng.choice(["Onderhoudsboekje aanwezig.", "Facturen aanwezig.", "1e eigenaar."]))
    if options:
        parts.append("Opties: " + ", ".join(OPTION_LABELS.get(o, o) for o in options) + ".")
    parts.extend(flags)
    parts.append("DEMO-advertentie, gegenereerd door Autozoeker.")
    return " ".join(parts)


def generate(n: int, seed: int = 42, now: datetime | None = None, history_days: int = 75,
             id_offset: int = 0) -> list[DemoCar]:
    rng = random.Random(seed)
    now = now or datetime(2026, 10, 27, 9, 0)
    taxonomy = load_taxonomy()
    entries = CATALOG
    weights = [e[2] for e in entries]
    cars: list[DemoCar] = []
    for i in range(n):
        make, model_slug, _pop, base_price, retention, trims = _weighted(rng, entries, weights)
        mdef = get_model(make, model_slug)
        assert mdef is not None, (make, model_slug)
        trim = rng.choice(trims)
        title_trim, fuel, kw, transmission, battery, trim_factor = trim[:6]
        trim_from, trim_to = trim[6] if len(trim) > 6 else (None, None)
        first_year = max(2012, min(g.year_from for g in mdef.generations), trim_from or 0)
        last_year = min(now.year, max((g.year_to or now.year) for g in mdef.generations), trim_to or 9999)
        if fuel == "elektrisch":
            first_year = max(first_year, 2014)
        first_year = min(first_year, last_year)
        year = rng.randint(first_year, last_year)
        month = rng.randint(1, 12) if year < now.year else rng.randint(1, max(1, now.month - 2))
        reg = date(year, month, rng.randint(1, 28))
        age_years = max(0.15, (now.date() - reg).days / 365.25)
        expected_km = age_years * ANNUAL_KM.get(fuel, 13000)
        km = int(max(500, expected_km * rng.lognormvariate(0, 0.38)))
        km = int(round(km, -2)) + rng.randint(0, 99)

        new_price = base_price * trim_factor * (1 - 0.02 * max(0, 2024 - year))
        value = _value(new_price, age_years, fuel, retention, km, expected_km)
        flags: list[str] = []
        battery_lease = False
        if model_slug == "zoe" and battery and battery <= 41 and rng.random() < 0.45:
            battery_lease = True
            value *= 0.55
            flags.append("Let op: huuraccu, batterijhuur ca. € 79 per maand.")
        noise = rng.lognormvariate(0, 0.06)
        r = rng.random()
        if r < 0.07:
            noise *= rng.uniform(0.74, 0.9)  # bargain (or a reason it is cheap)
        elif r < 0.12:
            noise *= rng.uniform(1.1, 1.25)
        dealer = rng.random() < 0.78
        price = _round_price(value * noise, dealer, rng)

        if rng.random() < 0.035:
            flags.append(rng.choice([
                "Export prijs.", "Zo meenemen, geen garantie.", "Handelsprijs.",
                "Motor maakt tikkend geluid bij koude start.", "Lichte schade aan achterbumper.",
            ]))

        options = sorted(rng.sample(OPTION_POOL, k=rng.randint(2, 8)))
        if mdef.segment in ("A",) and "trekhaak" in options:
            options.remove("trekhaak")
        if fuel == "elektrisch" and rng.random() < 0.5:
            options.append("warmtepomp")
        bovag = dealer and rng.random() < 0.6
        warranty = (rng.choice([3, 6, 12, 12, 24]) if dealer and rng.random() < 0.65 else None)
        seller_name = rng.choice(DEALER_NAMES) if dealer else rng.choice(PRIVATE_NAMES)
        colour = _weighted(rng, COLOURS, COLOUR_WEIGHTS)

        make_name = taxonomy[make].name
        title = f"{make_name} {title_trim}" if model_slug == make else f"{make_name} {mdef.name} {title_trim}"
        plate = f"DM{id_offset + i + 1:06d}"
        desc = _description(rng, {"bovag": bovag, "warranty": warranty}, options, dealer, flags)

        first_seen = now - timedelta(days=rng.uniform(0, history_days), hours=rng.uniform(0, 12))
        removed = None
        if rng.random() < 0.28:
            removed = first_seen + timedelta(days=rng.uniform(4, 45))
            if removed >= now:
                removed = None
        history = [(first_seen, price)]
        current = price
        t = first_seen
        end = removed or now
        while rng.random() < 0.35:
            t = t + timedelta(days=rng.uniform(6, 20))
            if t >= end:
                break
            current = _round_price(current * rng.uniform(0.94, 0.985), dealer, rng)
            history.append((t, current))

        raw = RawListing(
            source="demo",
            source_id=f"demo-{id_offset + i + 1}",
            url=f"https://example.invalid/demo/{id_offset + i + 1}",
            title=title,
            make_raw=make_name,
            model_raw=mdef.name,
            trim=title_trim,
            price_eur=current,
            mileage_km=km,
            first_registration=reg,
            year=year,
            fuel_raw={"benzine": "Benzine", "diesel": "Diesel", "elektrisch": "Elektrisch", "hybride": "Hybride",
                      "plugin_hybride": "Plug-in hybride", "lpg": "LPG"}[fuel],
            transmission_raw="Automaat" if transmission == "automaat" else "Handgeschakeld",
            body_raw=None,
            power_kw=kw,
            battery_kwh=battery,
            doors=3 if mdef.segment == "A" and rng.random() < 0.3 else 5,
            seats=7 if "7p" in title_trim else (4 if mdef.segment == "A" else 5),
            colour_raw=colour,
            kenteken=plate,
            seller_type="dealer" if dealer else "private",
            seller_name=seller_name,
            seller_bovag=bovag,
            warranty_months=warranty,
            postcode=_postcode(rng),
            image_urls=[],
            description=desc,
            options_raw=options,
            extra={"battery_lease": battery_lease},
            is_demo=True,
        )

        # RDW-like vehicle data
        is_import = rng.random() < 0.08
        nl_reg = reg + timedelta(days=rng.randint(180, 1500)) if is_import else reg
        if nl_reg > now.date():
            nl_reg = now.date() - timedelta(days=30)
        nap_r = rng.random()
        nap = "Logisch" if nap_r < 0.94 else ("Onlogisch" if nap_r < 0.97 else "Geen oordeel")
        recalls = []
        if rng.random() < 0.09:
            ref, title_r, defect = rng.choice(DEMO_RECALLS)
            open_ = rng.random() < 0.45
            recalls.append({
                "referentiecode_rdw": ref,
                "status": "Openstaande terugroepactie" if open_ else "Producent heeft herstel gemeld",
                "open": open_,
                "omschrijving_defect": defect,
                "titel": title_r,
                "demo": True,
            })
        apk_defects = []
        if age_years > 4:
            for _ in range(rng.randint(0, 3)):
                code, desc_d = rng.choice(DEMO_APK_DEFECTS)
                d = reg + timedelta(days=rng.randint(4 * 365, max(4 * 365 + 1, int(age_years * 365))))
                apk_defects.append({"datum": d.isoformat(), "code": code, "omschrijving": desc_d, "aantal": 1})
        mass = SEGMENT_MASS.get(mdef.segment, 1300) + (320 if fuel == "elektrisch" else 180 if fuel == "plugin_hybride" else 0)
        mass += rng.randint(-40, 60)
        tow = SEGMENT_TOW.get(mdef.segment, 1200)
        if fuel == "elektrisch":
            tow = int(tow * rng.choice([0, 0.6, 0.75, 1.0]))
        if model_slug in ("model-y", "id-4", "enyaq", "xc40"):
            tow = max(tow, 1000)
        kwh_100 = SEGMENT_KWH.get(mdef.segment, 17) if fuel == "elektrisch" else None
        l_100 = None
        if fuel in ("benzine", "lpg"):
            l_100 = SEGMENT_L.get(mdef.segment, 6) + kw / 400
        elif fuel == "diesel":
            l_100 = SEGMENT_L.get(mdef.segment, 6) - 1.2 + kw / 500
        elif fuel == "hybride":
            l_100 = SEGMENT_L.get(mdef.segment, 6) - 1.4
        elif fuel == "plugin_hybride":
            l_100 = 1.6
            kwh_100 = 16.0
        range_km = int(battery / kwh_100 * 100 * 0.93) if fuel == "elektrisch" and battery and kwh_100 else (
            int(battery / 18 * 100) if fuel == "plugin_hybride" and battery else None)
        taxi_p = 0.06 if model_slug in TAXI_PRONE else 0.008
        vehicle = {
            "kenteken": plate,
            "is_demo": True,
            "found": True,
            "make": make_name.upper(),
            "trade_name": mdef.name.upper(),
            "first_admission": reg,
            "first_nl_registration": nl_reg,
            "last_registration": nl_reg + timedelta(days=rng.randint(0, max(1, (now.date() - nl_reg).days))),
            "apk_expiry": _next_apk(reg, fuel, now.date(), rng) if age_years > 2.5 else _first_apk(reg, fuel),
            "is_import": is_import,
            "odometer_judgement": nap,
            "odometer_code": {"Logisch": "00", "Onlogisch": "05", "Geen oordeel": "99"}[nap],
            "odometer_explanation": {
                "Logisch": "De geregistreerde tellerstanden zijn logisch (DEMO).",
                "Onlogisch": "Er is een onlogische tellerstand geregistreerd (DEMO).",
                "Geen oordeel": "Te weinig tellerstanden voor een oordeel (DEMO).",
            }[nap],
            "odometer_last_year": now.year if rng.random() < 0.8 else now.year - 1,
            "open_recall": any(rc["open"] for rc in recalls),
            "taxi": rng.random() < taxi_p,
            "export": False,
            "insured": True,
            "catalog_price": int(new_price),
            "mass_empty": mass,
            "mass_ready": mass + 100,
            "towing_braked": tow,
            "towing_unbraked": min(750, int(mass / 2)) if tow else 0,
            "seats": raw.seats,
            "colour": colour.upper(),
            "body": None,
            "engine_cc": None,
            "fuel": fuel,
            "power_kw": float(kw),
            "co2_g_km": round(l_100 * 23.5, 0) if l_100 and fuel != "diesel" else (round(l_100 * 26.5, 0) if l_100 else 0),
            "consumption_l_100km": round(l_100, 1) if l_100 else None,
            "consumption_kwh_100km": round(kwh_100, 1) if kwh_100 else None,
            "range_km": range_km,
            "recalls": recalls,
            "apk_defects": sorted(apk_defects, key=lambda d: d["datum"], reverse=True),
        }
        cars.append(DemoCar(raw=raw, first_seen_at=first_seen, removed_at=removed, price_history=history,
                            vehicle=vehicle))
    return cars
