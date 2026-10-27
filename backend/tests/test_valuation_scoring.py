import copy

from sqlalchemy import select

from app.models import Listing
from app.scoring.components import composite, km_component, normalize_weights
from app.scoring.redflags import PHRASES
from app.search import pareto_frontier
from app.valuation.model import get_model_instance


def test_model_quality(seeded):
    m = get_model_instance()
    assert m is not None and m.metrics["rows"] >= 1000
    # synthetic data has ~6% noise plus deliberate outliers; median error should stay well below 15%
    assert m.metrics["median_ape_pct"] < 15


def test_value_decreases_with_km_and_age(seeded):
    m = get_model_instance()
    car = seeded.scalars(select(Listing).where(Listing.make == "volkswagen", Listing.model == "golf",
                                               Listing.mileage_km.is_not(None)).limit(1)).one()
    base = m.predict(car, use_oof=False).predicted
    more_km = copy.copy(car)
    more_km.id = -1
    more_km.mileage_km = car.mileage_km + 80000
    assert m.predict(more_km, use_oof=False).predicted < base
    later = m.project_value(car, 3, 15000)
    assert later < base


def test_km_effect_has_the_right_sign(seeded):
    rows = seeded.scalars(select(Listing).where(Listing.km_effect_eur.is_not(None), Listing.expected_km.is_not(None),
                                                Listing.mileage_km.is_not(None))).all()
    assert len(rows) > 500
    for r in rows:
        if r.mileage_km < r.expected_km:
            assert r.km_effect_eur >= 0, (r.id, r.mileage_km, r.expected_km, r.km_effect_eur)
        elif r.mileage_km > r.expected_km:
            assert r.km_effect_eur <= 0, (r.id, r.mileage_km, r.expected_km, r.km_effect_eur)


def test_deal_scores_and_components_present(seeded):
    rows = seeded.scalars(select(Listing).where(Listing.status == "active").limit(200)).all()
    assert all(r.score_components for r in rows)
    assert sum(1 for r in rows if r.deal_score is not None) > 150


def test_pareto_frontier():
    pts = [(1, 10000, 100000), (2, 12000, 60000), (3, 11000, 120000), (4, 15000, 30000), (5, 16000, 40000)]
    assert pareto_frontier(pts) == {1, 2, 4}


def test_weights_and_composite():
    w = normalize_weights({"deal": 1.0, "km": 0, "health": 0, "issues": 0, "seller": 0, "distance": 0})
    assert abs(w["deal"] - 1.0) < 1e-9
    assert composite({"deal": 1.0}, {"deal": 1, "km": 0, "health": 0, "issues": 0, "seller": 0, "distance": 0}) == 100
    assert composite({"deal": 0.0}, {"deal": 1, "km": 0, "health": 0, "issues": 0, "seller": 0, "distance": 0}) == 0


def test_km_component():
    car = Listing(mileage_km=30000, year=2020)
    low, _ = km_component(car, 60000)
    car.mileage_km = 150000
    high, ratio = km_component(car, 60000)
    assert low > high and ratio == 2.5


def test_redflag_phrases_do_not_fire_on_negations():
    import re

    damage = next(p for p in PHRASES if p[1] == "damage")[0]
    assert re.search(damage, "auto is schadevrij en heeft geen schade")is None
    assert re.search(damage, "lichte schade aan bumper")
