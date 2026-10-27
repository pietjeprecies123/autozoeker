"""RDW parsing against the dataset schema (column names from the rdw-data client)."""

import httpx

from app.enrich import rdw
from app.models import Vehicle

VEHICLE = {
    "kenteken": "AB123C", "voertuigsoort": "Personenauto", "merk": "VOLKSWAGEN", "handelsbenaming": "GOLF",
    "vervaldatum_apk": "20270315", "datum_tenaamstelling": "20230101", "inrichting": "hatchback",
    "aantal_zitplaatsen": "5", "eerste_kleur": "GRIJS", "cilinderinhoud": "1395", "massa_ledig_voertuig": "1205",
    "massa_rijklaar": "1305", "maximum_massa_trekken_ongeremd": "640", "maximum_trekken_massa_geremd": "1500",
    "datum_eerste_toelating": "20160302", "datum_eerste_tenaamstelling_in_nederland": "20180610",
    "catalogusprijs": "28490", "wam_verzekerd": "Ja", "export_indicator": "Nee",
    "openstaande_terugroepactie_indicator": "Ja", "taxi_indicator": "Nee", "tellerstandoordeel": "Logisch",
    "code_toelichting_tellerstandoordeel": "00", "jaar_laatste_registratie_tellerstand": "2025",
    "zuinigheidsclassificatie": "B",
}
FUEL = [{"kenteken": "AB123C", "brandstof_volgnummer": "1", "brandstof_omschrijving": "Benzine",
         "nettomaximumvermogen": "92.00", "brandstofverbruik_gecombineerd": "5.10", "co2_uitstoot_gecombineerd": "118",
         "uitlaatemissieniveau": "EURO 6 W"}]
STATUS = [{"kenteken": "AB123C", "referentiecode_rdw": "R123", "code_status": "O", "status": "Openstaande terugroepactie"}]
RECALL = [{"referentiecode_rdw": "R123", "omschrijving_defect": "Brandstofleiding kan lekken",
           "materi_le_gevolgen": "Brandgevaar", "beschrijving_van_het_herstel": "Leiding vervangen",
           "publicatiedatum_rdw": "20240501"}]
APK = [{"kenteken": "AB123C", "meld_datum_door_keuringsinstantie": "20250310", "gebrek_identificatie": "AC1",
        "aantal_gebreken_geconstateerd": "2", "soort_erkenning_omschrijving": "APK Lichte voertuigen"}]
GEBREKEN = [{"gebrek_identificatie": "AC1", "gebrek_omschrijving": "Band(en) profieldiepte onvoldoende"}]
TELLER = [{"code_toelichting_tellerstandoordeel": "00", "toelichting_tellerstandoordeel": "De tellerstand is logisch."}]


def handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    data = {
        "/resource/m9d7-ebf2.json": [VEHICLE] if request.url.params.get("kenteken") == "AB123C" else [],
        "/resource/8ys7-d773.json": FUEL,
        "/resource/t49b-isb7.json": STATUS,
        "/resource/j9yg-7rg9.json": RECALL,
        "/resource/a34c-vvps.json": APK,
        "/resource/hx2c-gt7k.json": GEBREKEN,
        "/resource/jqs4-4kvw.json": TELLER,
    }.get(path)
    return httpx.Response(200, json=data if data is not None else [])


def client():
    return rdw.RdwClient(base_url="https://opendata.rdw.nl/resource", app_token="", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_fetch_parses_everything():
    v = rdw.fetch("AB123C", client())
    assert v["found"] is True
    assert v["is_import"] is True  # first NL registration two years after first admission
    assert v["apk_expiry"].isoformat() == "2027-03-15"
    assert v["odometer_judgement"] == "Logisch"
    assert v["odometer_explanation"] == "De tellerstand is logisch."
    assert v["open_recall"] is True
    assert v["recalls"][0]["open"] is True and v["recalls"][0]["herstel"] == "Leiding vervangen"
    assert v["apk_defects"][0]["omschrijving"].startswith("Band")
    assert v["towing_braked"] == 1500 and v["mass_ready"] == 1305
    assert v["fuel"] == "benzine" and v["power_kw"] == 92.0
    assert v["catalog_price"] == 28490


def test_not_found():
    v = rdw.fetch("ZZ999Z", client())
    assert v["found"] is False


def test_canonical_fuel_variants():
    assert rdw.canonical_fuel([{"brandstof_omschrijving": "Elektriciteit"}]) == "elektrisch"
    assert rdw.canonical_fuel([{"brandstof_omschrijving": "Benzine"}, {"brandstof_omschrijving": "Elektriciteit",
                               "klasse_hybride_elektrisch_voertuig": "OVC-HEV"}]) == "plugin_hybride"
    assert rdw.canonical_fuel([{"brandstof_omschrijving": "Benzine"}, {"brandstof_omschrijving": "Elektriciteit",
                               "klasse_hybride_elektrisch_voertuig": "NOVC-HEV"}]) == "hybride"
    assert rdw.canonical_fuel([{"brandstof_omschrijving": "Diesel"}]) == "diesel"


def test_ev_consumption_units():
    v = rdw.parse_vehicle("X", VEHICLE, [{"brandstof_omschrijving": "Elektriciteit",
                                          "elektrisch_verbruik_enkel_elektrisch_wltp": "153",
                                          "actie_radius_enkel_elektrisch_wltp": "420"}], [], [], None)
    assert v["consumption_kwh_100km"] == 15.3 and v["range_km"] == 420


def test_enrich_caches(session, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "online_enrichment", True)
    v = rdw.enrich(session, "AB123C", client=client())
    assert isinstance(v, Vehicle) and v.found
    session.commit()
    # second call uses the cache: a failing client must not be hit
    def boom(request):
        raise AssertionError("should not fetch")
    failing = rdw.RdwClient(client=httpx.Client(transport=httpx.MockTransport(boom)))
    assert rdw.enrich(session, "AB123C", client=failing).kenteken == "AB123C"


def test_enrich_offline_returns_cache_or_none(session):
    assert rdw.enrich(session, "AB123C") is None  # ONLINE_ENRICHMENT=false and nothing cached
