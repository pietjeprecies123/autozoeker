"""Market-value model.

Primary: gradient boosting on log(price) over all listings seen (active and sold), with 10th/90th
percentile models for a value band. Deal scores for listings in the training set use out-of-fold
predictions, so a car is never valued by a model that has already seen its own price.

Fallbacks when there is too little data: a per-model hedonic regression log(price) ~ age + km, and
below that the median of the nearest comparables.
"""

from __future__ import annotations

import logging
import math
import pickle
import re
from dataclasses import dataclass
from datetime import datetime

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import KFold
from sklearn.preprocessing import OrdinalEncoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Listing
from app.normalize.taxonomy import get_model
from app.util import age_in_months, utcnow

log = logging.getLogger(__name__)

CAT_FEATURES = ["make", "make_model", "generation", "fuel", "transmission", "body", "segment"]
NUM_FEATURES = ["age_months", "km", "power_kw", "battery_kwh", "n_options", "battery_lease", "trim_level"]
MONOTONIC = {"age_months": -1, "km": -1}
MIN_TRAIN_ROWS = 200
DEFAULT_ANNUAL_KM = {"diesel": 21000, "elektrisch": 15000, "plugin_hybride": 16000, "hybride": 14500, "lpg": 19000}

_TRIM_UP = re.compile(r"\b(gt|gti|gtd|gte|gt-line|gt line|r-line|r line|s-line|s line|amg|m sport|m-sport|st-line|"
                      r"n line|sport|executive|high executive|highline|inscription|r-design|lounge|tekna|"
                      r"premium|style|elegance|luxury|performance|vrs|rs|fr|cupra)\b", re.I)
_TRIM_DOWN = re.compile(r"\b(trendline|base|basis|active|access|life|pure|essential|comfort|edition|"
                        r"standard|expression|pop|trend|ambition|acenta|light|cool)\b", re.I)


def trim_level(text: str | None) -> float:
    if not text:
        return 0.0
    return float(len(_TRIM_UP.findall(text))) - 0.5 * len(_TRIM_DOWN.findall(text))


def _row(listing: Listing, ref=None) -> dict:
    mdef = get_model(listing.make, listing.model)
    return {
        "make": listing.make or "",
        "make_model": f"{listing.make}/{listing.model}" if listing.model else "",
        "generation": listing.generation or "",
        "fuel": listing.fuel or "",
        "transmission": listing.transmission or "",
        "body": listing.body or "",
        "segment": mdef.segment if mdef else "",
        "age_months": age_in_months(listing.first_registration, listing.year, ref),
        "km": listing.mileage_km,
        "power_kw": listing.power_kw,
        "battery_kwh": listing.battery_kwh,
        "n_options": len(listing.options or []),
        "battery_lease": 1.0 if (listing.extra or {}).get("battery_lease") else 0.0,
        "trim_level": trim_level(listing.trim or listing.title),
    }


def _numeric(rows: list[dict]) -> np.ndarray:
    out = np.full((len(rows), len(NUM_FEATURES)), np.nan)
    for i, r in enumerate(rows):
        for j, f in enumerate(NUM_FEATURES):
            v = r.get(f)
            if v is not None:
                out[i, j] = float(v)
    return out


def trainable(listing: Listing) -> bool:
    return bool(
        listing.price_eur
        and 500 <= listing.price_eur <= 500_000
        and listing.price_type == "asking"
        and listing.mileage_km is not None
        and (listing.first_registration or listing.year)
        and listing.make
        and listing.model
    )


@dataclass
class Valuation:
    predicted: int
    low: int
    high: int
    method: str  # gbm | hedonic | comparables
    confidence: str  # high | medium | low
    km_effect_eur: int | None = None
    expected_km: int | None = None


class ValuationModel:
    def __init__(self):
        self.encoder: OrdinalEncoder | None = None
        self.median: HistGradientBoostingRegressor | None = None
        self.q10: HistGradientBoostingRegressor | None = None
        self.q90: HistGradientBoostingRegressor | None = None
        self.n_rows = 0
        self.model_counts: dict[str, int] = {}
        self.annual_km: dict[str, float] = {}
        self.trained_at: datetime | None = None
        self.oof: dict[int, float] = {}
        self.metrics: dict = {}

    # -- features -------------------------------------------------------------------------------
    def _matrix(self, rows: list[dict]) -> np.ndarray:
        assert self.encoder is not None
        cats = np.array([[r[f] for f in CAT_FEATURES] for r in rows], dtype=object)
        enc = self.encoder.transform(cats).astype(float)
        return np.hstack([enc, _numeric(rows)])

    def _new_gbm(self, loss: str = "squared_error", quantile: float | None = None) -> HistGradientBoostingRegressor:
        mask = [True] * len(CAT_FEATURES) + [False] * len(NUM_FEATURES)
        # Value never rises with age or km; without this, noise can make a low-km car "worth less".
        monotonic = [0] * len(CAT_FEATURES) + [MONOTONIC.get(f, 0) for f in NUM_FEATURES]
        kwargs = dict(max_iter=250, learning_rate=0.08, max_leaf_nodes=31, min_samples_leaf=12,
                      l2_regularization=0.5, categorical_features=mask, monotonic_cst=monotonic, random_state=7)
        if quantile is not None:
            return HistGradientBoostingRegressor(loss="quantile", quantile=quantile, **kwargs)
        return HistGradientBoostingRegressor(loss=loss, **kwargs)

    # -- training -------------------------------------------------------------------------------
    def fit(self, listings: list[Listing]) -> ValuationModel:
        listings = [x for x in listings if trainable(x)]
        self.n_rows = len(listings)
        self.model_counts = {}
        for x in listings:
            key = f"{x.make}/{x.model}"
            self.model_counts[key] = self.model_counts.get(key, 0) + 1
        self._fit_annual_km(listings)
        self.trained_at = utcnow()
        if len(listings) < MIN_TRAIN_ROWS:
            self.median = None
            return self
        rows = [_row(x) for x in listings]
        y = np.log(np.array([x.price_eur for x in listings], dtype=float))
        self.encoder = OrdinalEncoder(
            handle_unknown="use_encoded_value", unknown_value=np.nan, encoded_missing_value=np.nan, max_categories=250
        )
        self.encoder.fit(np.array([[r[f] for f in CAT_FEATURES] for r in rows], dtype=object))
        X = self._matrix(rows)

        # out-of-fold predictions for honest deal scores
        oof = np.zeros(len(listings))
        kf = KFold(n_splits=5, shuffle=True, random_state=11)
        for train_idx, test_idx in kf.split(X):
            m = self._new_gbm()
            m.fit(X[train_idx], y[train_idx])
            oof[test_idx] = m.predict(X[test_idx])
        self.oof = {x.id: float(math.exp(p)) for x, p in zip(listings, oof, strict=True)}
        ape = np.abs(np.exp(oof) - np.exp(y)) / np.exp(y)
        self.metrics = {
            "rows": len(listings),
            "mape_pct": round(float(np.mean(ape)) * 100, 1),
            "median_ape_pct": round(float(np.median(ape)) * 100, 1),
            "within_10pct": round(float(np.mean(ape <= 0.10)) * 100, 1),
        }

        self.median = self._new_gbm().fit(X, y)
        self.q10 = self._new_gbm(quantile=0.1).fit(X, y)
        self.q90 = self._new_gbm(quantile=0.9).fit(X, y)
        log.info("valuation model trained: %s", self.metrics)
        return self

    def _fit_annual_km(self, listings: list[Listing]) -> None:
        per_model: dict[str, list[float]] = {}
        for x in listings:
            age = age_in_months(x.first_registration, x.year)
            if age and age >= 12 and x.mileage_km:
                per_model.setdefault(f"{x.make}/{x.model}", []).append(x.mileage_km / (age / 12))
        self.annual_km = {k: float(np.median(v)) for k, v in per_model.items() if len(v) >= 5}

    # -- prediction -----------------------------------------------------------------------------
    def expected_km(self, listing: Listing) -> int | None:
        age = age_in_months(listing.first_registration, listing.year)
        if age is None:
            return None
        per_year = self.annual_km.get(f"{listing.make}/{listing.model}") or DEFAULT_ANNUAL_KM.get(listing.fuel or "", 13000)
        return int(per_year * age / 12)

    def _confidence(self, listing: Listing, low: float, high: float, pred: float) -> str:
        n = self.model_counts.get(f"{listing.make}/{listing.model}", 0)
        width = (high - low) / pred if pred else 1
        if n >= 30 and width < 0.35:
            return "high"
        if n >= 10 and width < 0.6:
            return "medium"
        return "low"

    def predict(self, listing: Listing, use_oof: bool = True) -> Valuation | None:
        if not (listing.make and listing.model and listing.mileage_km is not None and (listing.first_registration or listing.year)):
            return None
        if self.median is None or self.encoder is None:
            return None
        row = _row(listing)
        X = self._matrix([row])
        pred = float(math.exp(self.median.predict(X)[0]))
        if use_oof and listing.id in self.oof:
            pred = self.oof[listing.id]
        low = float(math.exp(self.q10.predict(X)[0])) if self.q10 else pred * 0.85
        high = float(math.exp(self.q90.predict(X)[0])) if self.q90 else pred * 1.15
        low, high = min(low, pred * 0.97), max(high, pred * 1.03)

        exp_km = self.expected_km(listing)
        km_effect = None
        if exp_km is not None and listing.mileage_km is not None:
            row_exp = dict(row, km=exp_km)
            at_expected = float(math.exp(self.median.predict(self._matrix([row_exp]))[0]))
            at_actual = float(math.exp(self.median.predict(X)[0]))
            km_effect = int(round(at_actual - at_expected))
        return Valuation(
            predicted=int(round(pred)),
            low=int(round(low)),
            high=int(round(high)),
            method="gbm",
            confidence=self._confidence(listing, low, high, pred),
            km_effect_eur=km_effect,
            expected_km=exp_km,
        )


    def predict_many(self, listings: list[Listing], use_oof: bool = True) -> dict[int, Valuation]:
        """Batched version of predict() (one model call per quantile instead of per car)."""
        if self.median is None or self.encoder is None:
            return {}
        ok = [x for x in listings if x.make and x.model and x.mileage_km is not None and (x.first_registration or x.year)]
        if not ok:
            return {}
        rows = [_row(x) for x in ok]
        X = self._matrix(rows)
        med = np.exp(self.median.predict(X))
        lo = np.exp(self.q10.predict(X)) if self.q10 else med * 0.85
        hi = np.exp(self.q90.predict(X)) if self.q90 else med * 1.15
        exp_kms = [self.expected_km(x) for x in ok]
        X_exp = self._matrix([dict(r, km=e if e is not None else r["km"]) for r, e in zip(rows, exp_kms, strict=True)])
        at_exp = np.exp(self.median.predict(X_exp))
        out: dict[int, Valuation] = {}
        for i, x in enumerate(ok):
            pred = self.oof.get(x.id, float(med[i])) if use_oof else float(med[i])
            low, high = min(float(lo[i]), pred * 0.97), max(float(hi[i]), pred * 1.03)
            out[x.id] = Valuation(
                predicted=int(round(pred)),
                low=int(round(low)),
                high=int(round(high)),
                method="gbm",
                confidence=self._confidence(x, low, high, pred),
                km_effect_eur=int(round(float(med[i]) - float(at_exp[i]))) if exp_kms[i] is not None else None,
                expected_km=exp_kms[i],
            )
        return out


    def project_value(self, listing: Listing, years: float, km_per_year: int) -> int | None:
        """Estimated market value after `years` more years and km (at today's market level)."""
        if self.median is None or self.encoder is None:
            return None
        row = _row(listing)
        if row["age_months"] is None or row["km"] is None:
            return None
        row = dict(row, age_months=row["age_months"] + int(years * 12), km=row["km"] + int(years * km_per_year))
        return int(round(math.exp(self.median.predict(self._matrix([row]))[0])))

    def depreciation_curve(self, listing: Listing, km_per_year: int = 13000, years: int = 5) -> list[dict]:
        """Projected value per year from now, anchored to the car's current market estimate."""
        values = [self.project_value(listing, y, km_per_year) for y in range(0, years + 1)]
        if not values or values[0] is None:
            return []
        scale = (listing.predicted_price / values[0]) if listing.predicted_price else 1.0
        return [{"year": y, "value": int(round(v * scale))} for y, v in enumerate(values) if v is not None]


def hedonic_or_comparables(listing: Listing, comps: list[Listing]) -> Valuation | None:
    """Small-data fallback using cars of the same make/model."""
    comps = [c for c in comps if c.id != listing.id and trainable(c)]
    age = age_in_months(listing.first_registration, listing.year)
    if age is None or listing.mileage_km is None or not comps:
        return None
    if len(comps) >= 8:
        A = np.array([[1.0, age_in_months(c.first_registration, c.year) or 0, c.mileage_km or 0] for c in comps])
        y = np.log(np.array([c.price_eur for c in comps], dtype=float))
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        resid = y - A @ coef
        sd = float(np.std(resid)) if len(resid) > 2 else 0.15
        pred = float(math.exp(coef[0] + coef[1] * age + coef[2] * listing.mileage_km))
        return Valuation(int(pred), int(pred * math.exp(-1.28 * sd)), int(pred * math.exp(1.28 * sd)),
                         "hedonic", "medium" if len(comps) >= 20 else "low")
    near = nearest(listing, comps, k=6)
    if not near:
        return None
    prices = sorted(c.price_eur for c in near)
    mid = prices[len(prices) // 2]
    return Valuation(int(mid), int(prices[0]), int(prices[-1]), "comparables", "low")


def nearest(listing: Listing, candidates: list[Listing], k: int = 12) -> list[Listing]:
    age = age_in_months(listing.first_registration, listing.year) or 0
    scored = []
    for c in candidates:
        if c.id == listing.id or not c.price_eur or c.mileage_km is None:
            continue
        c_age = age_in_months(c.first_registration, c.year)
        if c_age is None:
            continue
        d = ((c_age - age) / 12) ** 2 + ((c.mileage_km - (listing.mileage_km or 0)) / 25000) ** 2
        if listing.power_kw and c.power_kw:
            d += ((c.power_kw - listing.power_kw) / 30) ** 2
        if listing.fuel and c.fuel != listing.fuel:
            d += 2.0
        if listing.generation and c.generation != listing.generation:
            d += 0.5
        scored.append((d, c))
    scored.sort(key=lambda t: t[0])
    return [c for _, c in scored[:k]]


# -- singleton + persistence ----------------------------------------------------------------------
_model: ValuationModel | None = None


def _path():
    return get_settings().data_dir / "valuation.pkl"


def get_model_instance() -> ValuationModel | None:
    global _model
    if _model is None:
        p = _path()
        if p.exists():
            try:
                with p.open("rb") as fh:
                    _model = pickle.load(fh)
            except Exception:
                log.warning("could not load %s; retraining needed", p)
                _model = None
    return _model


def set_model_instance(model: ValuationModel | None) -> None:
    global _model
    _model = model


def train(session: Session, persist: bool = True) -> ValuationModel:
    q = select(Listing).where(Listing.price_eur.is_not(None))
    if not get_settings().demo_mode:
        q = q.where(Listing.is_demo.is_(False))  # generated demo prices must not value real cars
    listings = list(session.scalars(q))
    model = ValuationModel().fit(listings)
    set_model_instance(model)
    if persist:
        p = _path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("wb") as fh:
            pickle.dump(model, fh)
    return model
