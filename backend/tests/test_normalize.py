from datetime import date

import pytest

from app.demo.catalog import CATALOG
from app.normalize import kenteken, normalize_raw
from app.normalize.fields import extract_options, norm_body, norm_fuel, norm_transmission
from app.normalize.taxonomy import get_model, load_taxonomy, match_vehicle
from app.sources.base import RawListing
from app.util import parse_date, parse_int


@pytest.mark.parametrize("raw,expected", [
    ("ab-123-c", "AB123C"), ("12-AB-34", "12AB34"), ("1-ABC-23", "1ABC23"), ("ABC-12-D", "ABC12D"),
    ("XX-99-99", "XX9999"), ("AB12", None), ("ABCDEF", None), ("123456", None), ("", None),
])
def test_kenteken_normalize(raw, expected):
    assert kenteken.normalize(raw) == expected


def test_kenteken_format_and_extract():
    assert kenteken.format_plate("1ABC23") == "1-ABC-23"
    assert kenteken.format_plate("AB123C") == "AB-123-C"
    assert kenteken.extract("Mooie auto, kenteken: G-123-BB, NAP") == "G123BB"
    assert kenteken.extract("Dealer onderhouden. Kenteken XN-725-T bekijken?") == "XN725T"
    assert kenteken.extract("prijs 12-345 en 2.0 TDI") is None


@pytest.mark.parametrize("make,model,title,year,exp_make,exp_model,exp_gen", [
    ("Volkswagen", "Golf", "Volkswagen Golf 1.5 TSI Life", 2021, "volkswagen", "golf", "golf-8"),
    ("VW", "Golf Variant", "VW Golf Variant 1.6 TDI", 2016, "volkswagen", "golf", "golf-7"),
    (None, None, "Tesla Model 3 Long Range AWD", 2021, "tesla", "model-3", "model-3-1"),
    ("BMW", "320i", "BMW 320i Executive", 2018, "bmw", "3-serie", "3-serie-f30"),
    ("Mercedes-Benz", "A 180", "Mercedes-Benz A 180 Business", 2019, "mercedes-benz", "a-klasse", "a-w177"),
    ("Peugeot", "e-208", "Peugeot e-208 GT", 2021, "peugeot", "208", "208-2"),
    ("Mazda", "3", "Mazda 3 2.0 SkyActiv-G", 2020, "mazda", "3", "mazda3-bp"),
    ("Lynk & Co", "01", "Lynk & Co 01 1.5 PHEV", 2022, "lynk-co", "01", "lynk-01-1"),
    ("Škoda", "Octavia Combi", "Skoda Octavia Combi 1.0 TSI", 2019, "skoda", "octavia", "octavia-3"),
])
def test_match_vehicle(make, model, title, year, exp_make, exp_model, exp_gen):
    m = match_vehicle(make, model, title, year)
    assert m is not None
    assert (m.make, m.model, m.generation) == (exp_make, exp_model, exp_gen)


def test_hints_from_alias():
    m = match_vehicle("Peugeot", "e-208", "Peugeot e-208", 2021)
    assert m.fuel_hint == "elektrisch"
    m = match_vehicle("Volkswagen", "Golf Variant", None, 2018)
    assert m.body_hint == "stationwagen"


def test_every_demo_catalog_entry_round_trips():
    taxonomy = load_taxonomy()
    for make, model, *_ in CATALOG:
        md = get_model(make, model)
        assert md is not None, (make, model)
        title = f"{taxonomy[make].name} {md.name} trim"
        m = match_vehicle(taxonomy[make].name, md.name, title, md.generations[-1].year_from)
        assert (m.make, m.model) == (make, model), title


@pytest.mark.parametrize("raw,text,expected", [
    ("Benzine", "", "benzine"), ("Diesel", "", "diesel"), ("Elektrisch", "", "elektrisch"),
    ("Hybride (benzine/elektrisch)", "", "hybride"), ("Elektro/Benzine", "plug-in hybrid", "plugin_hybride"),
    ("LPG", "", "lpg"), (None, "golf 2.0 tdi", "diesel"), (None, "corolla 1.8 hybrid", "hybride"),
])
def test_norm_fuel(raw, text, expected):
    assert norm_fuel(raw, text) == expected


def test_norm_body_transmission_options():
    assert norm_body("Stationwagen") == "stationwagen"
    assert norm_body(None, "Audi A4 Avant 2.0 TDI") == "stationwagen"
    assert norm_body("SUV / Terreinwagen") == "suv"
    assert norm_transmission("Automaat") == "automaat"
    assert norm_transmission(None, "1.4 TSI DSG Highline") == "automaat"
    assert norm_transmission("Handgeschakeld") == "handgeschakeld"
    opts = extract_options("Trekhaak, Navigatie, climate control en stoelverwarming", "warmtepomp")
    assert {"trekhaak", "navigatie", "climate_control", "stoelverwarming", "warmtepomp"} <= set(opts)


def test_parsers():
    assert parse_int("€ 15.950,-") == 15950
    assert parse_int("123.456 km") == 123456
    assert parse_int(None) is None
    assert parse_date("20190612") == date(2019, 6, 12)
    assert parse_date("06-2019") == date(2019, 6, 1)
    assert parse_date("2019-06-12T00:00:00.000") == date(2019, 6, 12)


def test_normalize_raw_full():
    raw = RawListing(
        source="x", source_id="1", url="u", title="Volkswagen Golf 1.4 TSI DSG Highline", make_raw="Volkswagen",
        model_raw="Golf", price_eur=12345, mileage_km=88000, first_registration=date(2016, 3, 1),
        fuel_raw="Benzine", transmission_raw="Automaat", postcode="3511AB",
        description="Kenteken: KK-123-B. Trekhaak en navigatie. BOVAG garantie.",
    )
    f = normalize_raw(raw)
    assert f["make"] == "volkswagen" and f["model"] == "golf" and f["generation"] == "golf-7"
    assert f["kenteken"] == "KK123B"
    assert f["postcode"] == "3511"
    assert f["seller_bovag"] is True
    assert "trekhaak" in f["options"]
    assert f["engine_cc"] == 1400
    assert f["fingerprint"]
