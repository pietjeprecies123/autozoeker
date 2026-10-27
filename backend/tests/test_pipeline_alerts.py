from datetime import date, timedelta

from sqlalchemy import select

from app.alerts import engine, ntfy
from app.analysis import refresh
from app.demo.seed import demo_tick
from app.ingest.pipeline import IngestResult, ingest_many, mark_stale, upsert
from app.models import AlertSent, Listing, PriceHistory, Profile, SavedSearch, WatchlistItem
from app.sources.base import RawListing
from app.util import utcnow


def raw(source="autoscout24", sid="1", price=15000, plate="AB-123-C", **kw):
    return RawListing(source=source, source_id=sid, url=f"https://x/{sid}", title="Toyota Yaris 1.5 Hybrid Active",
                      make_raw="Toyota", model_raw="Yaris", price_eur=price, mileage_km=60000,
                      first_registration=date(2020, 5, 1), fuel_raw="Hybride", transmission_raw="Automaat",
                      postcode="3511", kenteken=plate, **kw)


def test_upsert_new_update_price_and_back(session):
    listing, outcome = upsert(session, raw(), enrich=False)
    assert outcome == "new" and listing.kenteken == "AB123C" and listing.group_id == listing.id
    _, outcome = upsert(session, raw(), enrich=False)
    assert outcome == "unchanged"
    _, outcome = upsert(session, raw(price=14500), enrich=False)
    assert outcome == "price"
    prices = session.scalars(select(PriceHistory.price_eur).where(PriceHistory.listing_id == listing.id)).all()
    assert prices == [15000, 14500]
    listing.status = "removed"
    _, outcome = upsert(session, raw(price=14500), enrich=False)
    assert outcome == "back"


def test_cross_site_dedupe_by_kenteken_and_fingerprint(session):
    a, _ = upsert(session, raw(source="autoscout24", sid="a1"), enrich=False)
    b, _ = upsert(session, raw(source="marktplaats", sid="m1", price=15200), enrich=False)
    assert b.group_id == a.id
    c, _ = upsert(session, raw(source="autoscout24", sid="a2", plate=None), enrich=False)
    d, _ = upsert(session, raw(source="marktplaats", sid="m2", plate=None, price=15300), enrich=False)
    assert d.group_id == (c.group_id or c.id)


def test_mark_stale(session):
    listing, _ = upsert(session, raw(), enrich=False)
    listing.last_seen_at = utcnow() - timedelta(days=5)
    removed = mark_stale(session, ["autoscout24"], max_age_hours=72)
    assert removed == [listing.id] and listing.status == "removed"


def test_ingest_many_isolates_errors(session):
    bad = raw(sid="bad")
    bad.first_registration = "not a date"  # will break the DB layer
    res = ingest_many(session, [raw(sid="ok"), bad], enrich=False)
    assert len(res.new) >= 1


def test_ntfy_payload():
    p = ntfy.build_payload("topic", "Titel", "Bericht", click="https://a", attach="https://img", tags=["car"],
                           actions=[{"action": "view", "label": "x", "url": "https://a"}])
    assert p["topic"] == "topic" and p["markdown"] is True and p["actions"][0]["action"] == "view"


def test_alerts_flow(seeded):
    sent: list[dict] = []
    profile = seeded.scalars(select(Profile)).first() or Profile(name="Pim")
    if profile.id is None:
        seeded.add(profile)
        seeded.flush()
    profile.ntfy_topic = "test-topic"
    search = SavedSearch(profile_id=profile.id, name="Alles", filters={}, min_match=0, alert_mode="instant")
    seeded.add(search)
    seeded.flush()
    result = demo_tick(seeded, new_count=5)
    refresh(seeded, result.touched)
    alerts = engine.process(seeded, result, publisher=lambda p: sent.append(p) or True)
    new_alerts = [a for a in alerts if a.kind == "new" and a.saved_search_id == search.id]
    assert len(new_alerts) == 5
    assert all(a.delivery == "sent" for a in new_alerts)
    assert sent and sent[0]["topic"] == "test-topic" and "In Autozoeker" in str(sent[0]["actions"])
    # processing the same result again must not alert twice
    again = engine.process(seeded, result, publisher=lambda p: sent.append(p) or True)
    assert not [a for a in again if a.kind == "new" and a.saved_search_id == search.id]


def test_watchlist_alert_and_digest(seeded):
    profile = Profile(name="Tester", ntfy_topic="t2")
    seeded.add(profile)
    seeded.flush()
    watched = select(WatchlistItem.listing_id)
    listing = seeded.scalars(select(Listing).where(Listing.status == "active", Listing.id.not_in(watched))).first()
    seeded.add(WatchlistItem(listing_id=listing.id, added_by=profile.id))
    old = listing.price_eur
    listing.price_eur = old - 500
    seeded.add(PriceHistory(listing_id=listing.id, price_eur=listing.price_eur))
    seeded.flush()
    sent = []
    alerts = engine.process(seeded, IngestResult(price_changed=[listing.id]), publisher=lambda p: sent.append(p) or True)
    assert any(a.kind == "price_drop" and a.listing_id == listing.id for a in alerts)

    search = SavedSearch(profile_id=profile.id, name="Dagelijks", filters={}, min_match=0, alert_mode="daily")
    seeded.add(search)
    seeded.flush()
    res = demo_tick(seeded, new_count=3)
    refresh(seeded, res.touched)
    queued = [a for a in engine.process(seeded, res, publisher=lambda p: True) if a.saved_search_id == search.id]
    assert queued and all(a.delivery == "digest" for a in queued)
    digests = []
    assert engine.send_digests(seeded, publisher=lambda p: digests.append(p) or True) >= 1
    assert any("nieuwe matches" in d["title"] for d in digests)
    assert not seeded.scalars(select(AlertSent).where(AlertSent.delivery == "digest", AlertSent.profile_id == profile.id)).all()
