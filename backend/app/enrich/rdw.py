"""RDW open data (opendata.rdw.nl, Socrata) client and vehicle enrichment.

Datasets (IDs and column names taken from the maintained `rdw-data` client, v0.9.12):
  m9d7-ebf2  Gekentekende voertuigen               – base vehicle record, APK, NAP verdict, indicators
  8ys7-d773  Gekentekende voertuigen brandstof     – fuel(s), power, consumption, WLTP range, CO2
  t49b-isb7  Terugroep actie status                – recalls per kenteken + whether repaired
  j9yg-7rg9  Terugroep actie                       – recall details per RDW reference
  a34c-vvps  Geconstateerde gebreken               – defects found at APK inspections
  hx2c-gt7k  Gebreken                              – defect code descriptions
  jqs4-4kvw  Tellerstandoordeel trend toelichting  – explanation of the odometer verdict code
"""

from __future__ import annotations

import logging
import time
from datetime import timedelta

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Vehicle
from app.util import parse_date, parse_int, utcnow

log = logging.getLogger(__name__)

DATASETS = {
    "voertuigen": "m9d7-ebf2",
    "brandstof": "8ys7-d773",
    "recall_status": "t49b-isb7",
    "recall": "j9yg-7rg9",
    "apk_gebreken": "a34c-vvps",
    "gebreken": "hx2c-gt7k",
    "teller_toelichting": "jqs4-4kvw",
}


class RdwUnavailable(Exception):
    pass


def _yes(value) -> bool | None:
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in ("ja", "j", "yes", "true", "1"):
        return True
    if s in ("nee", "n", "no", "false", "0"):
        return False
    return None


def _float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _quote_list(values) -> str:
    return ",".join("'" + str(v).replace("'", "''") + "'" for v in values)


class RdwClient:
    def __init__(self, base_url: str | None = None, app_token: str | None = None, client: httpx.Client | None = None):
        settings = get_settings()
        self.base_url = (base_url or settings.rdw_base_url).rstrip("/")
        headers = {"Accept": "application/json"}
        token = app_token if app_token is not None else settings.rdw_app_token
        if token:
            headers["X-App-Token"] = token
        self.client = client or httpx.Client(timeout=15.0, headers=headers)

    def _get(self, key: str, params: dict) -> list[dict]:
        url = f"{self.base_url}/{DATASETS[key]}.json"
        try:
            resp = self.client.get(url, params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise RdwUnavailable(f"RDW {key}: {exc}") from exc
        data = resp.json()
        return data if isinstance(data, list) else []

    def vehicle(self, kenteken: str) -> dict | None:
        rows = self._get("voertuigen", {"kenteken": kenteken})
        return rows[0] if rows else None

    def fuels(self, kenteken: str) -> list[dict]:
        rows = self._get("brandstof", {"kenteken": kenteken})
        return sorted(rows, key=lambda r: parse_int(r.get("brandstof_volgnummer")) or 0)

    def recall_status(self, kenteken: str) -> list[dict]:
        return self._get("recall_status", {"kenteken": kenteken})

    def recall_details(self, refs: list[str]) -> dict[str, dict]:
        if not refs:
            return {}
        rows = self._get("recall", {"$where": f"referentiecode_rdw in({_quote_list(refs)})", "$limit": 100})
        return {r.get("referentiecode_rdw"): r for r in rows}

    def apk_defects(self, kenteken: str) -> list[dict]:
        rows = self._get("apk_gebreken", {"kenteken": kenteken, "$limit": 200})
        ids = sorted({r.get("gebrek_identificatie") for r in rows if r.get("gebrek_identificatie")})
        descriptions: dict[str, str] = {}
        if ids:
            for d in self._get("gebreken", {"$where": f"gebrek_identificatie in({_quote_list(ids)})", "$limit": 500}):
                descriptions[d.get("gebrek_identificatie")] = d.get("gebrek_omschrijving") or ""
        out = []
        for r in rows:
            d = parse_date(r.get("meld_datum_door_keuringsinstantie"))
            code = r.get("gebrek_identificatie")
            out.append(
                {
                    "datum": d.isoformat() if d else None,
                    "code": code,
                    "omschrijving": descriptions.get(code, ""),
                    "aantal": parse_int(r.get("aantal_gebreken_geconstateerd")) or 1,
                    "keuring": r.get("soort_erkenning_omschrijving"),
                }
            )
        return sorted(out, key=lambda x: x["datum"] or "", reverse=True)

    def odometer_explanation(self, code: str | None) -> str | None:
        if not code:
            return None
        rows = self._get("teller_toelichting", {"code_toelichting_tellerstandoordeel": code})
        return rows[0].get("toelichting_tellerstandoordeel") if rows else None


def canonical_fuel(fuel_rows: list[dict]) -> str | None:
    kinds = [str(r.get("brandstof_omschrijving", "")).lower() for r in fuel_rows]
    if not kinds:
        return None
    has_elec = any("elektr" in k for k in kinds)
    others = [k for k in kinds if "elektr" not in k]
    if has_elec and not others:
        return "elektrisch"
    if has_elec and others:
        classes = " ".join(str(r.get("klasse_hybride_elektrisch_voertuig") or "") for r in fuel_rows).upper()
        if "OVC" in classes and "NOVC" not in classes:
            return "plugin_hybride"
        if any(parse_int(r.get("actie_radius_extern_opladen_wltp")) for r in fuel_rows):
            return "plugin_hybride"
        return "hybride"
    main = others[0]
    for key, canon in (("benzine", "benzine"), ("diesel", "diesel"), ("lpg", "lpg"), ("cng", "cng"),
                       ("waterstof", "waterstof"), ("alcohol", "benzine")):
        if key in main:
            return canon
    return None


def parse_vehicle(kenteken: str, base: dict | None, fuel_rows: list[dict], recalls: list[dict],
                  apk_defects: list[dict], odometer_text: str | None) -> dict:
    if not base:
        return {"kenteken": kenteken, "found": False, "raw": {}}
    first_adm = parse_date(base.get("datum_eerste_toelating"))
    first_nl = parse_date(base.get("datum_eerste_tenaamstelling_in_nederland"))
    is_import = None
    if first_adm and first_nl:
        is_import = (first_nl - first_adm).days > 31

    kw = None
    l_100 = None
    kwh_100 = None
    range_km = None
    co2 = None
    emission = None
    for r in fuel_rows:
        kw = kw or _float(r.get("nettomaximumvermogen")) or _float(r.get("netto_max_vermogen_elektrisch"))
        l_100 = l_100 or _float(r.get("brandstof_verbruik_gecombineerd_wltp")) or _float(r.get("brandstofverbruik_gecombineerd"))
        ev = _float(r.get("elektrisch_verbruik_enkel_elektrisch_wltp")) or _float(r.get("elektriciteitsverbruik_volledig_elektrisch"))
        if ev and not kwh_100:
            # RDW reports Wh/km; older records may hold kWh/100 km
            kwh_100 = round(ev / 10, 1) if ev > 50 else ev
        rng = parse_int(r.get("actie_radius_enkel_elektrisch_wltp")) or parse_int(r.get("actie_radius_extern_opladen_wltp")) or parse_int(r.get("actieradius"))
        range_km = range_km or rng
        co2 = co2 or _float(r.get("emissie_co2_gecombineerd_wltp")) or _float(r.get("co2_uitstoot_gecombineerd"))
        emission = emission or r.get("uitlaatemissieniveau") or r.get("emissiecode_omschrijving")
    fuel = canonical_fuel(fuel_rows)

    return {
        "kenteken": kenteken,
        "found": True,
        "make": base.get("merk"),
        "trade_name": base.get("handelsbenaming"),
        "first_admission": first_adm,
        "first_nl_registration": first_nl,
        "last_registration": parse_date(base.get("datum_tenaamstelling")),
        "apk_expiry": parse_date(base.get("vervaldatum_apk")),
        "is_import": is_import,
        "odometer_judgement": base.get("tellerstandoordeel"),
        "odometer_code": base.get("code_toelichting_tellerstandoordeel"),
        "odometer_explanation": odometer_text,
        "odometer_last_year": parse_int(base.get("jaar_laatste_registratie_tellerstand")),
        "open_recall": _yes(base.get("openstaande_terugroepactie_indicator"))
        if base.get("openstaande_terugroepactie_indicator") is not None
        else any(rc.get("open") for rc in recalls),
        "taxi": _yes(base.get("taxi_indicator")),
        "export": _yes(base.get("export_indicator")),
        "insured": _yes(base.get("wam_verzekerd")),
        "catalog_price": parse_int(base.get("catalogusprijs")),
        "mass_empty": parse_int(base.get("massa_ledig_voertuig")),
        "mass_ready": parse_int(base.get("massa_rijklaar")),
        "towing_braked": parse_int(base.get("maximum_trekken_massa_geremd")),
        "towing_unbraked": parse_int(base.get("maximum_massa_trekken_ongeremd")),
        "seats": parse_int(base.get("aantal_zitplaatsen")),
        "colour": base.get("eerste_kleur"),
        "body": base.get("inrichting"),
        "engine_cc": parse_int(base.get("cilinderinhoud")),
        "fuel": fuel,
        "power_kw": kw,
        "co2_g_km": co2,
        "consumption_l_100km": l_100,
        "consumption_kwh_100km": kwh_100,
        "range_km": range_km,
        "energy_label": base.get("zuinigheidsclassificatie"),
        "emission_class": emission,
        "recalls": recalls,
        "apk_defects": apk_defects,
        "raw": {"voertuig": base, "brandstof": fuel_rows},
    }


def fetch(kenteken: str, client: RdwClient | None = None) -> dict:
    client = client or RdwClient()
    base = client.vehicle(kenteken)
    if not base:
        return parse_vehicle(kenteken, None, [], [], [], None)
    fuel_rows = client.fuels(kenteken)
    status_rows = client.recall_status(kenteken)
    details = client.recall_details([r.get("referentiecode_rdw") for r in status_rows if r.get("referentiecode_rdw")])
    recalls = []
    for r in status_rows:
        ref = r.get("referentiecode_rdw")
        d = details.get(ref, {})
        status = r.get("status") or ""
        published = parse_date(d.get("publicatiedatum_rdw"))
        recalls.append(
            {
                "referentiecode_rdw": ref,
                "status": status,
                "open": "openstaand" in status.lower(),
                "omschrijving_defect": d.get("omschrijving_defect"),
                "gevolgen": d.get("materi_le_gevolgen"),
                "herstel": d.get("beschrijving_van_het_herstel"),
                "categorie": d.get("categorie_defect"),
                "publicatiedatum": published.isoformat() if published else None,
                "producent": d.get("meldende_producent_distributeur"),
                "meer_info": d.get("meer_informatie_op_internet"),
            }
        )
    apk = client.apk_defects(kenteken)
    odometer_text = client.odometer_explanation(base.get("code_toelichting_tellerstandoordeel"))
    return parse_vehicle(kenteken, base, fuel_rows, recalls, apk, odometer_text)


_down_until = 0.0


def enrich(session: Session, kenteken: str, force: bool = False, client: RdwClient | None = None) -> Vehicle | None:
    """Return a fresh-enough Vehicle for this kenteken, fetching from RDW if needed.

    Never raises on network trouble: returns the cached record (possibly stale) or None.
    """
    global _down_until
    settings = get_settings()
    existing = session.get(Vehicle, kenteken)
    if existing and existing.is_demo:
        return existing
    fresh = existing and existing.fetched_at > utcnow() - timedelta(days=settings.rdw_cache_days)
    if fresh and not force:
        return existing
    if not settings.online_enrichment or (time.monotonic() < _down_until and client is None):
        return existing
    try:
        data = fetch(kenteken, client)
    except RdwUnavailable as exc:
        log.info("RDW unavailable (%s); using cache", exc)
        if client is None:
            _down_until = time.monotonic() + 600
        return existing
    data["fetched_at"] = utcnow()
    vehicle = existing or Vehicle(kenteken=kenteken)
    for key, value in data.items():
        setattr(vehicle, key, value)
    if not existing:
        session.add(vehicle)
    session.flush()
    return vehicle


def vehicle_to_dict(v: Vehicle | None) -> dict | None:
    if v is None:
        return None
    return {
        "kenteken": v.kenteken,
        "found": v.found,
        "is_demo": v.is_demo,
        "make": v.make,
        "trade_name": v.trade_name,
        "first_admission": v.first_admission,
        "first_nl_registration": v.first_nl_registration,
        "last_registration": v.last_registration,
        "apk_expiry": v.apk_expiry,
        "is_import": v.is_import,
        "odometer_judgement": v.odometer_judgement,
        "odometer_code": v.odometer_code,
        "odometer_explanation": v.odometer_explanation,
        "odometer_last_year": v.odometer_last_year,
        "open_recall": v.open_recall,
        "taxi": v.taxi,
        "export": v.export,
        "insured": v.insured,
        "catalog_price": v.catalog_price,
        "mass_empty": v.mass_empty,
        "mass_ready": v.mass_ready,
        "towing_braked": v.towing_braked,
        "towing_unbraked": v.towing_unbraked,
        "seats": v.seats,
        "colour": v.colour,
        "body": v.body,
        "engine_cc": v.engine_cc,
        "fuel": v.fuel,
        "power_kw": v.power_kw,
        "co2_g_km": v.co2_g_km,
        "consumption_l_100km": v.consumption_l_100km,
        "consumption_kwh_100km": v.consumption_kwh_100km,
        "range_km": v.range_km,
        "energy_label": v.energy_label,
        "emission_class": v.emission_class,
        "recalls": v.recalls or [],
        "apk_defects": v.apk_defects or [],
        "fetched_at": v.fetched_at,
    }
