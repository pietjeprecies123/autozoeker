from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.util import utcnow


class Listing(Base):
    """One advert on one source. The same car on two sites is two listings sharing a group_id."""

    __tablename__ = "listing"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_listing_source"),
        Index("ix_listing_make_model", "make", "model"),
        Index("ix_listing_status_price", "status", "price_eur"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str] = mapped_column(String(128))
    url: Mapped[str] = mapped_column(String(1024), default="")
    title: Mapped[str] = mapped_column(String(512), default="")

    # Canonical identity (slugs from app/normalize/taxonomy.yaml)
    make: Mapped[str | None] = mapped_column(String(64), index=True)
    model: Mapped[str | None] = mapped_column(String(64))
    generation: Mapped[str | None] = mapped_column(String(64))
    trim: Mapped[str | None] = mapped_column(String(256))
    make_raw: Mapped[str | None] = mapped_column(String(128))
    model_raw: Mapped[str | None] = mapped_column(String(128))

    kenteken: Mapped[str | None] = mapped_column(String(8), index=True)
    year: Mapped[int | None] = mapped_column(Integer)
    first_registration: Mapped[date | None] = mapped_column(Date)
    mileage_km: Mapped[int | None] = mapped_column(Integer)
    price_eur: Mapped[int | None] = mapped_column(Integer)
    price_type: Mapped[str] = mapped_column(String(16), default="asking")

    fuel: Mapped[str | None] = mapped_column(String(24))
    transmission: Mapped[str | None] = mapped_column(String(24))
    body: Mapped[str | None] = mapped_column(String(24))
    power_kw: Mapped[int | None] = mapped_column(Integer)
    engine_cc: Mapped[int | None] = mapped_column(Integer)
    battery_kwh: Mapped[float | None] = mapped_column(Float)
    doors: Mapped[int | None] = mapped_column(Integer)
    seats: Mapped[int | None] = mapped_column(Integer)
    colour: Mapped[str | None] = mapped_column(String(32))
    options: Mapped[list] = mapped_column(JSON, default=list)

    seller_type: Mapped[str | None] = mapped_column(String(16))
    seller_name: Mapped[str | None] = mapped_column(String(256))
    seller_bovag: Mapped[bool] = mapped_column(Boolean, default=False)
    warranty_months: Mapped[int | None] = mapped_column(Integer)

    postcode: Mapped[str | None] = mapped_column(String(8))
    city: Mapped[str | None] = mapped_column(String(128))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)

    image_urls: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text, default="")
    extra: Mapped[dict] = mapped_column(JSON, default=dict)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16), default="active")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    group_id: Mapped[int | None] = mapped_column(Integer, index=True)

    # Valuation & scoring cache (recomputed by app/valuation + app/scoring)
    predicted_price: Mapped[int | None] = mapped_column(Integer)
    predicted_low: Mapped[int | None] = mapped_column(Integer)
    predicted_high: Mapped[int | None] = mapped_column(Integer)
    valuation_method: Mapped[str | None] = mapped_column(String(24))
    valuation_confidence: Mapped[str | None] = mapped_column(String(8))
    deal_score: Mapped[float | None] = mapped_column(Float)
    km_effect_eur: Mapped[int | None] = mapped_column(Integer)
    expected_km: Mapped[int | None] = mapped_column(Integer)
    score_components: Mapped[dict] = mapped_column(JSON, default=dict)
    red_flags: Mapped[list] = mapped_column(JSON, default=list)
    valued_at: Mapped[datetime | None] = mapped_column(DateTime)

    prices: Mapped[list[PriceHistory]] = relationship(
        back_populates="listing", cascade="all, delete-orphan", order_by="PriceHistory.observed_at"
    )

    @property
    def age_months(self) -> int | None:
        from app.util import age_in_months

        return age_in_months(self.first_registration, self.year)


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listing.id", ondelete="CASCADE"), index=True)
    price_eur: Mapped[int] = mapped_column(Integer)
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    listing: Mapped[Listing] = relationship(back_populates="prices")


class Vehicle(Base):
    """RDW open-data snapshot for one kenteken."""

    __tablename__ = "vehicle"

    kenteken: Mapped[str] = mapped_column(String(8), primary_key=True)
    found: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    make: Mapped[str | None] = mapped_column(String(64))
    trade_name: Mapped[str | None] = mapped_column(String(128))
    first_admission: Mapped[date | None] = mapped_column(Date)
    first_nl_registration: Mapped[date | None] = mapped_column(Date)
    last_registration: Mapped[date | None] = mapped_column(Date)
    apk_expiry: Mapped[date | None] = mapped_column(Date)
    is_import: Mapped[bool | None] = mapped_column(Boolean)
    odometer_judgement: Mapped[str | None] = mapped_column(String(64))
    odometer_code: Mapped[str | None] = mapped_column(String(16))
    odometer_explanation: Mapped[str | None] = mapped_column(Text)
    odometer_last_year: Mapped[int | None] = mapped_column(Integer)
    open_recall: Mapped[bool | None] = mapped_column(Boolean)
    taxi: Mapped[bool | None] = mapped_column(Boolean)
    export: Mapped[bool | None] = mapped_column(Boolean)
    insured: Mapped[bool | None] = mapped_column(Boolean)
    catalog_price: Mapped[int | None] = mapped_column(Integer)
    mass_empty: Mapped[int | None] = mapped_column(Integer)
    mass_ready: Mapped[int | None] = mapped_column(Integer)
    towing_braked: Mapped[int | None] = mapped_column(Integer)
    towing_unbraked: Mapped[int | None] = mapped_column(Integer)
    seats: Mapped[int | None] = mapped_column(Integer)
    colour: Mapped[str | None] = mapped_column(String(32))
    body: Mapped[str | None] = mapped_column(String(64))
    engine_cc: Mapped[int | None] = mapped_column(Integer)
    fuel: Mapped[str | None] = mapped_column(String(64))
    power_kw: Mapped[float | None] = mapped_column(Float)
    co2_g_km: Mapped[float | None] = mapped_column(Float)
    consumption_l_100km: Mapped[float | None] = mapped_column(Float)
    consumption_kwh_100km: Mapped[float | None] = mapped_column(Float)
    range_km: Mapped[int | None] = mapped_column(Integer)
    energy_label: Mapped[str | None] = mapped_column(String(4))
    emission_class: Mapped[str | None] = mapped_column(String(32))
    recalls: Mapped[list] = mapped_column(JSON, default=list)
    apk_defects: Mapped[list] = mapped_column(JSON, default=list)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Profile(Base):
    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    home_postcode: Mapped[str | None] = mapped_column(String(8))
    ntfy_topic: Mapped[str | None] = mapped_column(String(128))
    weights: Mapped[dict] = mapped_column(JSON, default=dict)
    learned_weights: Mapped[dict] = mapped_column(JSON, default=dict)


class SavedSearch(Base):
    __tablename__ = "saved_search"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profile.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    weights: Mapped[dict] = mapped_column(JSON, default=dict)
    alert_mode: Mapped[str] = mapped_column(String(16), default="instant")  # instant | daily | off
    min_match: Mapped[int] = mapped_column(Integer, default=60)
    price_drop_eur: Mapped[int] = mapped_column(Integer, default=250)
    price_drop_pct: Mapped[float] = mapped_column(Float, default=2.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_digest_at: Mapped[datetime | None] = mapped_column(DateTime)


class AlertSent(Base):
    __tablename__ = "alert"
    __table_args__ = (
        UniqueConstraint("profile_id", "saved_search_id", "listing_id", "kind", "price_eur", name="uq_alert"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profile.id", ondelete="CASCADE"), index=True)
    saved_search_id: Mapped[int | None] = mapped_column(ForeignKey("saved_search.id", ondelete="CASCADE"))
    listing_id: Mapped[int] = mapped_column(ForeignKey("listing.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # new | price_drop | back | sold
    price_eur: Mapped[int | None] = mapped_column(Integer)
    match_score: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)
    delivery: Mapped[str] = mapped_column(String(16), default="pending")  # pending | sent | digest | failed | skipped
    seen: Mapped[bool] = mapped_column(Boolean, default=False)


class WatchlistItem(Base):
    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("listing_id", name="uq_watch_listing"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listing.id", ondelete="CASCADE"))
    added_by: Mapped[int | None] = mapped_column(ForeignKey("profile.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(24), default="interessant")
    notes: Mapped[str] = mapped_column(Text, default="")
    checklist_state: Mapped[dict] = mapped_column(JSON, default=dict)
    price_at_add: Mapped[int | None] = mapped_column(Integer)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (UniqueConstraint("profile_id", "listing_id", name="uq_feedback"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profile.id", ondelete="CASCADE"))
    listing_id: Mapped[int] = mapped_column(ForeignKey("listing.id", ondelete="CASCADE"))
    value: Mapped[int] = mapped_column(Integer)  # +1 / -1
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class IssueResearch(Base):
    """Cached AI research for a make/model/generation not covered by the curated knowledge base."""

    __tablename__ = "issue_research"

    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    make: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(64))
    generation: Mapped[str | None] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    model_used: Mapped[str] = mapped_column(String(64), default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    web_searches: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CrawlRun(Base):
    __tablename__ = "crawl_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    query_key: Mapped[str] = mapped_column(String(256), default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16), default="running")  # running | ok | partial | blocked | error
    n_fetched: Mapped[int] = mapped_column(Integer, default=0)
    n_new: Mapped[int] = mapped_column(Integer, default=0)
    n_updated: Mapped[int] = mapped_column(Integer, default=0)
    n_errors: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")


class AppSetting(Base):
    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict | list | str | int | float | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
