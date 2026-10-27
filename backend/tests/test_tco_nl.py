from datetime import date

from app.ai.nl_search import rule_based
from app.models import Listing, Vehicle
from app.scoring.negotiation import advise
from app.tco.mrb import estimate_quarter, province_for_postcode
from app.tco.tco import TcoInput, compute


def test_province_mapping():
    assert province_for_postcode("3511") == "Utrecht"
    assert province_for_postcode("1012AB") == "Noord-Holland"
    assert province_for_postcode("2511") == "Zuid-Holland"
    assert province_for_postcode("9711") == "Groningen"
    assert province_for_postcode(None) is None


def test_mrb_rules():
    petrol = estimate_quarter(1300, "benzine", "Utrecht")["quarter"]
    assert estimate_quarter(1300, "diesel", "Utrecht")["quarter"] > petrol * 1.9
    assert abs(estimate_quarter(1300, "elektrisch", "Utrecht")["quarter"] - petrol * 0.7) < 0.05
    assert estimate_quarter(1500, "benzine", "Utrecht")["quarter"] > petrol
    assert estimate_quarter(1300, "benzine", "Utrecht", first_registration=date(1980, 1, 1))["quarter"] == 0
    assert estimate_quarter(1300, "benzine", "Zuid-Holland")["quarter"] > estimate_quarter(1300, "benzine", "Noord-Holland")["quarter"]
    assert estimate_quarter(None, "benzine", None)["quarter"] is None


def test_tco_breakdown():
    car = Listing(price_eur=20000, fuel="elektrisch", power_kw=150, year=2021, first_registration=date(2021, 1, 1),
                  mileage_km=40000)
    v = Vehicle(kenteken="X", consumption_kwh_100km=16.0, mass_ready=1900)
    out = compute(car, v, TcoInput(km_per_year=15000, years=3), "3511", lambda y, k: 14000)
    m = out["monthly"]
    assert abs(m["totaal"] - sum(v for k, v in m.items() if k != "totaal")) < 0.05
    assert out["consumption"]["source"] == "RDW" and out["resale_value"] == 14000
    assert out["mrb"]["province"] == "Utrecht"


def test_negotiation_never_above_asking():
    car = Listing(price_eur=20495, predicted_price=27264, predicted_low=20517, seller_type="dealer", prices=[],
                  first_seen_at=None, warranty_months=12)
    adv = advise(car, None, [], [])
    assert adv["walk_away"] <= 20495 and adv["opening_bid"] <= adv["walk_away"]


def test_rule_based_nl_search():
    f, notes = rule_based("zuinige gezinsauto onder 15k met trekhaak voor 1500 kg, automaat")
    assert f.price_max == 15000 and f.towing_min == 1500 and f.transmissions == ["automaat"]
    assert "trekhaak" in f.options and set(f.bodies) == {"stationwagen", "suv", "mpv"}
    f, _ = rule_based("Toyota Corolla hybride max 100.000 km vanaf 2019 onder € 22.500")
    assert f.models == ["toyota/corolla"] and f.km_max == 100000 and f.year_min == 2019 and f.price_max == 22500
    f, _ = rule_based("golf variant diesel tot 12000 euro")
    assert f.models == ["volkswagen/golf"] and f.fuels == ["diesel"] and f.price_max == 12000
