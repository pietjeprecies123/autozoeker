"""Rule-based red flags: things to double-check before you drive out to see a car."""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Listing, Vehicle
from app.normalize.taxonomy import find_make
from app.util import age_in_months, today, utcnow

SEVERITY_PENALTY = {"high": 0.08, "medium": 0.03, "low": 0.01, "info": 0.0}

PHRASES: list[tuple[str, str, str, str]] = [
    # (regex, code, severity, explanation)
    (r"\bexport(prijs| prijs|handel)?\b", "export", "high", "Advertentie noemt export: vaak schade, geen garantie of geen NAP."),
    (r"handelsprijs|handelaarsprijs|meeneemprijs", "trade_price", "medium", "Handelsprijs: meestal zonder garantie en 'zoals hij is'."),
    (r"zo meenemen|zoals (hij|ie) is|voor de handel|opknapper", "as_is", "medium", "Verkocht zoals hij is: reken op reparatiekosten."),
    (r"geen garantie", "no_warranty", "low", "Expliciet geen garantie."),
    (r"start niet|rijdt niet|loopt niet|motor (defect|kapot)|motorschade|koppakking", "not_running", "high", "Technisch defect genoemd."),
    (r"tikkend geluid|tikt|rammel|maakt geluid|lekt olie|olieverbruik", "noise", "medium", "Geluid of lekkage genoemd: laat het vooraf keuren."),
    (r"versnellingsbak (defect|maakt|slaat)|schakelt (slecht|hard)|koppeling (slipt|versleten)", "gearbox", "high", "Problemen met versnellingsbak/koppeling genoemd."),
    (r"(?<!geen )(?<!zonder )\bschade\b|schadeauto|hagelschade|aanrijdingsschade", "damage", "medium", "Schade genoemd: vraag foto's en herstelfacturen."),
    (r"huuraccu|batterijhuur|accuhuur|batterij ?huur|battery lease", "battery_lease", "medium", "Huuraccu: de accu is geen eigendom; vraag het huurcontract en de maandkosten."),
    (r"western union|alleen whatsapp|auto staat in (het )?buitenland|verzending via|aanbetaling vooraf", "scam_pattern", "high", "Patroon dat vaak bij oplichting hoort. Nooit vooraf betalen."),
    (r"\bmarge\b", "margin", "info", "Marge-auto (geen btw verrekenbaar) – alleen relevant voor zakelijke kopers."),
]


def _flag(code: str, severity: str, title: str, detail: str = "") -> dict:
    return {"code": code, "severity": severity, "title": title, "detail": detail}


def _fuel_family(fuel: str | None) -> str | None:
    if fuel in ("hybride", "plugin_hybride"):
        return "hybrid"
    return fuel


def context(session: Session) -> dict:
    """Pre-aggregated counts so compute() needs no per-listing queries during bulk refreshes."""
    private_counts = {
        (src, name): n
        for src, name, n in session.execute(
            select(Listing.source, Listing.seller_name, func.count())
            .where(Listing.seller_type == "private", Listing.status == "active", Listing.seller_name.is_not(None))
            .group_by(Listing.source, Listing.seller_name)
        )
    }
    removed_by_plate = {
        plate: n
        for plate, n in session.execute(
            select(Listing.kenteken, func.count())
            .where(Listing.status == "removed", Listing.kenteken.is_not(None))
            .group_by(Listing.kenteken)
        )
    }
    return {"private_counts": private_counts, "removed_by_plate": removed_by_plate}


def compute(session: Session, listing: Listing, vehicle: Vehicle | None, ctx: dict | None = None) -> list[dict]:
    ctx = ctx if ctx is not None else context(session)
    flags: list[dict] = []
    desc = f"{listing.title} {listing.description or ''}".lower()

    if listing.deal_score is not None and listing.deal_score > 0.25 and listing.valuation_confidence != "low":
        flags.append(_flag("price_too_low", "high", "Prijs ver onder marktwaarde",
                           f"{int(listing.deal_score * 100)}% onder de geschatte marktwaarde. Een koopje kan, maar check extra goed "
                           "waarom: schade, import, huuraccu, of een nep-advertentie."))

    if listing.kenteken and vehicle is not None:
        if not vehicle.found:
            flags.append(_flag("plate_unknown", "high", "Kenteken onbekend bij RDW",
                               "Het kenteken uit de advertentie bestaat niet in het RDW-register."))
        else:
            rdw_make = find_make(vehicle.make)
            if rdw_make and listing.make and rdw_make != listing.make:
                flags.append(_flag("rdw_make_mismatch", "high", "Merk wijkt af van RDW",
                                   f"Advertentie: {listing.make}, RDW: {vehicle.make}."))
            if vehicle.first_admission and (listing.first_registration or listing.year):
                listed_year = listing.first_registration.year if listing.first_registration else listing.year
                if abs(vehicle.first_admission.year - listed_year) >= 2:
                    flags.append(_flag("rdw_year_mismatch", "medium", "Bouwjaar wijkt af van RDW",
                                       f"Advertentie: {listed_year}, eerste toelating RDW: {vehicle.first_admission.year}."))
            if vehicle.fuel and listing.fuel and _fuel_family(vehicle.fuel) != _fuel_family(listing.fuel):
                flags.append(_flag("rdw_fuel_mismatch", "medium", "Brandstof wijkt af van RDW",
                                   f"Advertentie: {listing.fuel}, RDW: {vehicle.fuel}."))
            nap = (vehicle.odometer_judgement or "").lower()
            if "onlogisch" in nap:
                flags.append(_flag("nap_illogical", "high", "NAP-oordeel onlogisch",
                                   vehicle.odometer_explanation or "De kilometerstand is mogelijk teruggedraaid of onvolledig."))
            if vehicle.is_import:
                mentioned = re.search(r"import|geïmporteerd|geimporteerd|uit (duitsland|belgië|belgie|frankrijk)", desc)
                flags.append(_flag("import", "low" if mentioned else "medium",
                                   "Importauto" + ("" if mentioned else " (niet vermeld in advertentie)"),
                                   "Kilometerhistorie van vóór de import staat niet in de NAP. Vraag buitenlandse "
                                   "onderhoudshistorie en eventueel een Car-Pass/Carfax."))
            if vehicle.open_recall:
                flags.append(_flag("open_recall", "medium", "Openstaande terugroepactie",
                                   "Laat de dealer de recall vóór aflevering (gratis) uitvoeren."))
            if vehicle.taxi:
                flags.append(_flag("ex_taxi", "medium", "Ex-taxi", "Zwaar gebruikt; check slijtage en onderhoud extra goed."))
            if vehicle.export:
                flags.append(_flag("export_indicator", "high", "RDW-exportindicator",
                                   "Het voertuig staat bij de RDW als geëxporteerd geregistreerd."))
            if vehicle.apk_expiry:
                days = (vehicle.apk_expiry - today()).days
                if days < 0:
                    flags.append(_flag("apk_expired", "medium", "APK verlopen", f"Sinds {vehicle.apk_expiry.isoformat()}."))
                elif days < 60:
                    flags.append(_flag("apk_soon", "low", "APK verloopt binnenkort",
                                       f"Op {vehicle.apk_expiry.isoformat()}: vraag om nieuwe APK bij aflevering."))

    for pattern, code, severity, detail in PHRASES:
        if re.search(pattern, desc):
            if code == "battery_lease" and (listing.extra or {}).get("battery_lease") is False:
                continue
            title = {
                "export": "Export genoemd", "trade_price": "Handelsprijs", "as_is": "Verkocht zoals hij is",
                "no_warranty": "Geen garantie", "not_running": "Defect genoemd", "noise": "Geluid/lekkage genoemd",
                "gearbox": "Versnellingsbak/koppeling", "damage": "Schade genoemd", "battery_lease": "Huuraccu",
                "scam_pattern": "Mogelijke oplichting", "margin": "Marge-auto",
            }[code]
            flags.append(_flag(code, severity, title, detail))
    if (listing.extra or {}).get("battery_lease") and not any(f["code"] == "battery_lease" for f in flags):
        flags.append(_flag("battery_lease", "medium", "Huuraccu", PHRASES[8][3]))

    if listing.seller_type == "private" and listing.seller_name and listing.seller_name.lower() != "particulier":
        count = ctx["private_counts"].get((listing.source, listing.seller_name), 0)
        if count >= 3:
            flags.append(_flag("private_many_ads", "medium", "Particulier met veel advertenties",
                               f"{count} actieve advertenties: mogelijk een handelaar die zich als particulier voordoet "
                               "(dan geen garantieplicht)."))

    if listing.kenteken:
        relists = ctx["removed_by_plate"].get(listing.kenteken, 0) - (1 if listing.status == "removed" else 0)
        if relists >= 1:
            flags.append(_flag("relisted", "low", "Eerder aangeboden",
                               f"Dit kenteken is al {relists}× eerder aangeboden en weer offline gehaald."))

    days_online = (utcnow() - listing.first_seen_at).days if listing.first_seen_at else 0
    if days_online >= 45 and listing.status == "active":
        flags.append(_flag("long_on_market", "info", f"{days_online} dagen online",
                           "Lang te koop: er is waarschijnlijk onderhandelingsruimte."))
    drops = max(0, len(listing.prices) - 1) if listing.prices else 0
    if drops >= 2:
        flags.append(_flag("price_drops", "info", f"{drops}× in prijs verlaagd", "Verkoper wil van de auto af."))

    age = age_in_months(listing.first_registration, listing.year)
    if age and age >= 12 and listing.mileage_km:
        per_year = listing.mileage_km / (age / 12)
        if per_year > 40000:
            flags.append(_flag("high_km_per_year", "info", f"{int(per_year / 1000)}k km per jaar",
                               "Veel snelweg-kilometers zijn niet per se slecht, maar check slijtagedelen."))
    return flags


def penalty(flags: list[dict]) -> float:
    return min(0.25, sum(SEVERITY_PENALTY.get(f["severity"], 0) for f in flags))
