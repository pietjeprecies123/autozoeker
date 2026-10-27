from fastapi.testclient import TestClient
from sqlalchemy import select

from app import db
from app.main import app, ensure_profiles
from app.models import Listing, Profile


def client(seeded_engine):
    db.set_engine(seeded_engine)
    ensure_profiles()
    return TestClient(app)


def test_search_detail_and_friends(seeded_engine):
    c = client(seeded_engine)
    meta = c.get("/api/meta").json()
    assert meta["demo_mode"] and {p["name"] for p in meta["profiles"]} >= {"Pim", "Eline"}
    pid = meta["profiles"][0]["id"]
    r = c.post("/api/search", json={"filters": {"price_max": 25000}, "sort": "best", "profile_id": pid, "page_size": 10})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] > 0 and len(data["items"]) <= 10 and data["pareto"]
    assert all(i["price_eur"] <= 25000 for i in data["items"])
    matches = [i["match"] for i in data["items"]]
    assert matches == sorted(matches, reverse=True)
    lid = data["items"][0]["id"]
    det = c.get(f"/api/listings/{lid}?profile_id={pid}").json()
    for key in ("vehicle", "issues", "comparables", "negotiation", "depreciation", "price_history"):
        assert key in det
    assert c.get(f"/api/listings/{lid}/checklist").json()["sections"]
    assert c.post(f"/api/listings/{lid}/tco", json={"km_per_year": 15000}).json()["monthly"]["totaal"] > 0
    plate = det["kenteken"]
    assert c.get(f"/api/kenteken/{plate}").json()["vehicle"]["is_demo"] is True
    ids = [i["id"] for i in data["items"][:2]]
    assert len(c.post("/api/compare", json={"ids": ids}).json()["items"]) == 2
    csv = c.post("/api/search/export.csv", json={"filters": {"price_max": 25000}}).text
    assert csv.splitlines()[0].startswith("﻿id;titel")


def test_saved_search_watchlist_feed(seeded_engine):
    c = client(seeded_engine)
    pid = c.get("/api/profiles").json()[0]["id"]
    s = c.post("/api/saved-searches", json={"profile_id": pid, "name": "Yaris", "filters": {"models": ["toyota/yaris"]}})
    assert s.status_code == 200
    lst = c.get(f"/api/saved-searches?profile_id={pid}").json()
    assert any(x["name"] == "Yaris" for x in lst)
    with db.session_scope() as session:
        lid = session.scalar(select(Listing.id).where(Listing.status == "active").limit(1))
    w = c.post("/api/watchlist", json={"listing_id": lid, "profile_id": pid}).json()
    assert c.put(f"/api/watchlist/{w['id']}", json={"status": "bezichtiging", "notes": "za 10:00"}).json()["ok"]
    assert c.put(f"/api/watchlist/{w['id']}", json={"status": "onzin"}).status_code == 400
    items = c.get("/api/watchlist").json()["items"]
    assert any(i["watch"]["status"] == "bezichtiging" for i in items)
    assert "items" in c.get(f"/api/feed?profile_id={pid}").json()
    assert c.post(f"/api/listings/{lid}/feedback", json={"profile_id": pid, "value": 1}).json()["ok"]


def test_parse_search_rules_and_ai_unavailable(seeded_engine):
    c = client(seeded_engine)
    r = c.post("/api/ai/parse-search", json={"text": "elektrische suv onder 30k"}).json()
    assert r["engine"] == "rules" and r["filters"]["price_max"] == 30000
    assert c.post("/api/issues/kia/picanto/research").status_code == 503
    assert c.get("/api/issues/tesla/model-3").json()["overview"]["issues"]
    assert c.get("/api/status").json()["valuation"]["rows"] > 0
    assert c.get("/api/insights/toyota?model=yaris").json()["active"] > 0


def test_basic_auth_keeps_health_open(seeded_engine, monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "basic_auth_user", "pim")
    monkeypatch.setattr(settings, "basic_auth_password", "geheim")
    c = client(seeded_engine)
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/meta").status_code == 401
    assert c.get("/api/meta", auth=("pim", "fout")).status_code == 401
    assert c.get("/api/meta", auth=("pim", "geheim")).status_code == 200


def test_detail_and_compare_score_like_search_with_learned_weights(seeded_engine):
    c = client(seeded_engine)
    pid = c.get("/api/profiles").json()[1]["id"]
    learned = {"deal": 0.05, "km": 0.6, "health": 0.1, "issues": 0.1, "seller": 0.1, "distance": 0.05}
    with db.session_scope() as session:
        session.get(Profile, pid).learned_weights = learned
    try:
        item = c.post("/api/search", json={"profile_id": pid, "page_size": 1}).json()["items"][0]
        default = c.get(f"/api/listings/{item['id']}").json()["match"]
        assert default != item["match"]  # the learned weights matter for this car
        assert c.get(f"/api/listings/{item['id']}?profile_id={pid}").json()["match"] == item["match"]
        compared = c.post("/api/compare", json={"ids": [item["id"]], "profile_id": pid}).json()["items"][0]
        assert compared["match"] == item["match"]
    finally:
        with db.session_scope() as session:
            session.get(Profile, pid).learned_weights = {}


def test_input_validation(seeded_engine):
    c = client(seeded_engine)
    pid = c.get("/api/profiles").json()[0]["id"]
    with db.session_scope() as session:
        lid = session.scalar(select(Listing.id).where(Listing.status == "active").limit(1))
    assert c.post(f"/api/listings/{lid}/tco", json={"years": 0}).status_code == 422
    assert c.post("/api/compare", json={"ids": [lid], "km_per_year": -1}).status_code == 422
    assert c.post("/api/saved-searches", json={"profile_id": pid, "name": "x", "min_match": 150}).status_code == 422
    s = c.post("/api/saved-searches", json={"profile_id": pid, "name": "Validatie"}).json()
    body = {"profile_id": pid, "name": "Validatie", "alert_mode": "weekly"}
    assert c.put(f"/api/saved-searches/{s['id']}", json=body).status_code == 422
    c.delete(f"/api/saved-searches/{s['id']}")


def test_csv_export_is_safe_for_dutch_excel(seeded_engine):
    from app.api.search_routes import _csv_cell

    assert _csv_cell(76.3) == "76,3" and _csv_cell(12) == 12
    assert _csv_cell("=HYPERLINK(\"http://x\")") == "'=HYPERLINK(\"http://x\")" and _csv_cell("Golf") == "Golf"
    c = client(seeded_engine)
    rows = [r.split(";") for r in c.post("/api/search/export.csv", json={"filters": {}}).text.splitlines()[1:50]]
    deals = [r[9] for r in rows if r[9]]
    assert deals and all("." not in d for d in deals) and any("," in d for d in deals)


def test_demo_rows_stay_out_of_real_valuations(seeded_engine, monkeypatch):
    from app.api.listing_routes import _comparables
    from app.config import get_settings
    from app.valuation.model import get_model_instance, set_model_instance, train

    monkeypatch.setattr(get_settings(), "demo_mode", False)
    db.set_engine(seeded_engine)
    session = db.SessionLocal()
    old_model = get_model_instance()
    try:
        assert train(session, persist=False).n_rows == 0  # only demo rows in this database
        demo = session.scalar(select(Listing).where(Listing.is_demo.is_(True), Listing.make == "toyota").limit(1))
        real = Listing(source="manual", source_id="real-1", title=demo.title, make=demo.make, model=demo.model,
                       year=demo.year, mileage_km=demo.mileage_km, price_eur=demo.price_eur, is_demo=False)
        session.add(real)
        session.flush()
        assert _comparables(session, real) == []
        assert _comparables(session, demo)
    finally:
        session.rollback()
        session.close()
        set_model_instance(old_model)

