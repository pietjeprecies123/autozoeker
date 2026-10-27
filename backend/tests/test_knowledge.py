from datetime import date

from app.knowledge import ev, service
from app.models import Listing, Vehicle
from app.normalize.taxonomy import get_model, load_taxonomy

SEVERITIES = {"low", "medium", "high", "critical"}
LIKELIHOODS = {"low", "medium", "high"}
FIX_TYPES = {"recall", "campaign", "revised_part", "software", "warranty_extension", "maintenance", "none"}


def test_all_files_valid():
    gens = {g.id for mk in load_taxonomy().values() for md in mk.models.values() for g in md.generations}
    seen = set()
    files = service.load_files()
    assert len(files) >= 20
    for f in files:
        for t in f.get("applies_to", []):
            assert get_model(t["make"], t.get("model")), (f["id"], t)
        assert all(isinstance(x, str) for x in f.get("general_checks", []) or []), f["id"]
        for i in f.get("issues", []):
            assert i["id"] not in seen, i["id"]
            seen.add(i["id"])
            assert i["severity"] in SEVERITIES and i["likelihood"] in LIKELIHOODS, i["id"]
            assert i["fix"]["type"] in FIX_TYPES, i["id"]
            assert i.get("sources") and all(s["url"].startswith("http") for s in i["sources"]), i["id"]
            assert i.get("questions"), i["id"]
            # a "key: value" inside an unquoted YAML list item silently becomes a mapping
            for key in ("symptoms", "verify", "questions", "test_drive"):
                assert all(isinstance(x, str) for x in i.get(key, []) or []), (i["id"], key)
            for key in ("title", "summary"):
                assert isinstance(i.get(key, ""), str), (i["id"], key)
            assert isinstance(i["fix"].get("description", ""), str), i["id"]
            for g in i.get("generations", []) or []:
                assert g in gens, (i["id"], g)
            for t in i.get("applies_to", []) or []:
                assert get_model(t["make"], t.get("model")), (i["id"], t)


def _car(**kw):
    defaults = dict(make="peugeot", model="208", generation="208-2", year=2019, first_registration=date(2019, 5, 1),
                    fuel="benzine", transmission="handgeschakeld", title="Peugeot 208 1.2 PureTech Allure",
                    trim="1.2 PureTech Allure", engine_cc=1200, options=[], extra={}, red_flags=[])
    defaults.update(kw)
    return Listing(**defaults)


def test_puretech_matches_and_excludes():
    ids = {m.issue["id"] for m in service.issues_for(_car())}
    assert "puretech-wet-belt" in ids
    ev_car = _car(fuel="elektrisch", title="Peugeot e-208 GT", trim="GT", engine_cc=None)
    assert "puretech-wet-belt" not in {m.issue["id"] for m in service.issues_for(ev_car)}
    diesel = _car(fuel="diesel", title="Peugeot 208 1.5 BlueHDi", trim="1.5 BlueHDi", engine_cc=1500)
    assert "puretech-wet-belt" not in {m.issue["id"] for m in service.issues_for(diesel)}


def test_unknown_engine_is_possible_not_certain():
    car = _car(title="Peugeot 208 Allure", trim="Allure", engine_cc=None)
    m = next(m for m in service.issues_for(car) if m.issue["id"] == "puretech-wet-belt")
    assert m.certainty == "mogelijk"


def test_opel_generation_filter():
    corsa_e = _car(make="opel", model="corsa", generation="corsa-e", year=2017, first_registration=date(2017, 1, 1),
                   title="Opel Corsa 1.4 Online Edition", trim="1.4 Online Edition", engine_cc=1400)
    assert not [m for m in service.issues_for(corsa_e) if m.issue["id"].startswith("puretech")]
    corsa_f = _car(make="opel", model="corsa", generation="corsa-f", year=2021, first_registration=date(2021, 1, 1),
                   title="Opel Corsa 1.2 Turbo Elegance", trim="1.2 Turbo Elegance")
    assert any(m.issue["id"] == "puretech-wet-belt-opel" for m in service.issues_for(corsa_f))


def test_dsg_only_for_automatic():
    golf = dict(make="volkswagen", model="golf", generation="golf-7", year=2016, first_registration=date(2016, 1, 1),
                title="Volkswagen Golf 1.4 TSI DSG Highline", trim="1.4 TSI DSG Highline", engine_cc=1400)
    assert any(m.issue["id"] == "dq200-mechatronic" for m in service.issues_for(_car(**golf, transmission="automaat")))
    assert not any(m.issue["id"] == "dq200-mechatronic" for m in service.issues_for(_car(**golf, transmission="handgeschakeld")))


def test_recall_state_from_rdw():
    kona = _car(make="hyundai", model="kona", generation="kona-1", year=2019, first_registration=date(2019, 3, 1),
                fuel="elektrisch", title="Hyundai Kona Electric 64 kWh", trim="Electric 64 kWh", engine_cc=None)
    v = Vehicle(kenteken="X", recalls=[{"referentiecode_rdw": "R1", "status": "Producent heeft herstel gemeld",
                                        "open": False, "omschrijving_defect": "Kortsluiting in de hoogvoltage batterij"}])
    m = next(m for m in service.issues_for(kona, v) if m.issue["id"] == "kona-ev-battery-recall")
    assert m.recall_status == "hersteld" and m.recall_refs == ["R1"]
    v.recalls[0]["open"] = True
    m2 = next(m for m in service.issues_for(kona, v) if m.issue["id"] == "kona-ev-battery-recall")
    assert m2.recall_status == "open"
    assert m.expected_cost < m2.expected_cost or m2.expected_cost <= 150


def test_risk_and_overview():
    score, cost, n = service.risk(_car())
    assert 0 <= score < 1 and cost > 0 and n >= 1
    ov = service.model_overview("tesla", "model-3")
    assert ov and ov["battery_warranty"]["years"] == 8 and ov["has_model_specific"]


def test_ev_info():
    tesla = _car(make="tesla", model="model-3", generation="model-3-1", fuel="elektrisch", year=2021,
                 first_registration=date(2021, 6, 1), mileage_km=60000, battery_kwh=75, title="Tesla Model 3 LR",
                 trim="Long Range", engine_cc=None, options=["warmtepomp"])
    info = ev.info(tesla, None)
    assert info["warranty_is_default"] is False and info["warranty_covered"] is True
    assert info["range"]["winter"] < info["range"]["wltp"]
    assert ev.info(_car(), None) is None


def test_ai_files_used_only_without_curated():
    service.set_ai_files([{"id": "ai-kia-picanto", "applies_to": [{"make": "kia", "model": "picanto"}],
                           "issues": [{"id": "x", "title": "t", "severity": "low", "likelihood": "low", "source": "ai"}]}])
    try:
        assert service.files_for("kia", "picanto")[0]["id"] == "ai-kia-picanto"
        assert all(f["id"] != "ai-kia-picanto" for f in service.files_for("tesla", "model-3"))
    finally:
        service.set_ai_files([])
