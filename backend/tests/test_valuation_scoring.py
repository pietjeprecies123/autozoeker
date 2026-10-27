import copy

import pytest
from sqlalchemy import select

from app.models import Listing
from app.scoring.components import composite, km_component, normalize_weights
from app.scoring.redflags import PHRASES, compute
from app.search import pareto_frontier
from app.util import price_drops
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


@pytest.mark.parametrize("text,expected", [
    ("Auto is schadevrij en heeft geen schade", set()),
    ("Lichte schade aan bumper", {"damage"}),
    ("Geen export!", set()),
    ("Niet voor export of handel", set()),
    ("Exportprijs, zo meenemen", {"export", "as_is"}),
    ("Rijdt niet alleen zuinig maar ook comfortabel", set()),
    ("Motor loopt niet onrustig", set()),
    ("Start niet altijd goed", {"not_running"}),
    ("Accu gekocht, geen huuraccu", set()),
    ("Inclusief huuraccu", {"battery_lease"}),
])
def test_redflag_phrases_respect_negation(text, expected):
    listing = Listing(title="Renault Zoe", description=text, prices=[])
    codes = {f["code"] for f in compute(None, listing, None, {"private_counts": {}, "removed_by_plate": {}})}
    assert codes & {p[1] for p in PHRASES} == expected


def test_price_drops_ignore_increases():
    assert price_drops([15000, 15500, 15000, 14500]) == 2
    assert price_drops([10000]) == 0 and price_drops(None) == 0
