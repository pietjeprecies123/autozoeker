from datetime import date, timedelta

from sqlalchemy import select

from app.alerts import engine, ntfy
from app.analysis import refresh
from app.demo.seed import demo_tick
from app.ingest.pipeline import IngestResult, blocked_until, confirm_stale, crawl, ingest_many, upsert
from app.models import AlertSent, CrawlRun, Listing, PriceHistory, Profile, SavedSearch, WatchlistItem
from app.sources.base import RawListing, SourceBlocked, SourceQuery
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


class FakeAdapter:
    name = "autoscout24"
    label = "fake"
    verified = True

    def __init__(self, online=(), blocked=False):
        self.online = set(online)
        self.blocked = blocked
        self.checked: list[str] = []

    def search(self, query):
        if self.blocked:
            raise SourceBlocked("429 from example")
        return iter(())

    def detail(self, url_or_id):
        self.checked.append(url_or_id)
        if self.blocked:
            raise SourceBlocked("429 from example")
        sid = url_or_id.rsplit("/", 1)[-1]
        return raw(sid=sid, plate=None) if sid in self.online else None

    def supports_url(self, url):
        return False


def test_confirm_stale_checks_the_advert_before_removing(session):
    old = utcnow() - timedelta(days=5)
    gone, _ = upsert(session, raw(sid="gone", plate=None), enrich=False)
    alive, _ = upsert(session, raw(sid="alive", plate=None), enrich=False)
    fresh, _ = upsert(session, raw(sid="fresh", plate=None), enrich=False)
    watched, _ = upsert(session, raw(sid="watched", plate=None), enrich=False)
    for listing in (gone, alive, watched):
        listing.last_seen_at = old
    session.add(WatchlistItem(listing_id=watched.id))
    session.flush()
    adapter = FakeAdapter(online={"alive", "watched"})
    res = confirm_stale(session, adapter, max_age_hours=72)
    assert adapter.checked[0].endswith("/watched")  # watched cars are checked first
    assert "https://x/fresh" not in adapter.checked
    assert res.removed == [gone.id] and gone.status == "removed"
    assert alive.status == "active" and alive.last_seen_at > old
    assert watched.status == "active"


def test_blocked_source_backs_off_and_keeps_listings(session):
    listing, _ = upsert(session, raw(sid="kept", plate=None), enrich=False)
    listing.last_seen_at = utcnow() - timedelta(days=5)
    adapter = FakeAdapter(blocked=True)
    assert crawl(session, adapter, SourceQuery(make="toyota")).blocked
    first = blocked_until(session, "autoscout24")
    assert first is not None and timedelta(minutes=55) < first - utcnow() <= timedelta(minutes=60)
    res = confirm_stale(session, adapter)
    assert res.blocked and listing.status == "active"
    second = blocked_until(session, "autoscout24")
    assert timedelta(minutes=115) < second - utcnow() <= timedelta(minutes=120)  # doubles
    session.add(CrawlRun(source="autoscout24", status="ok", finished_at=utcnow()))
    session.flush()
    assert blocked_until(session, "autoscout24") is None


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
