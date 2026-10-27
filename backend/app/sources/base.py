"""Source adapter contract.

Each listing site gets one adapter that turns a `SourceQuery` into `RawListing`s. Adapters do no
normalisation beyond parsing; app/normalize does the rest so all sources are treated the same.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Protocol

import httpx

from app.config import get_settings


@dataclass
class SourceQuery:
    make: str | None = None  # canonical slug
    model: str | None = None  # canonical slug
    text: str | None = None  # free text fallback
    price_min: int | None = None
    price_max: int | None = None
    km_max: int | None = None
    year_min: int | None = None
    fuel: str | None = None  # canonical fuel
    max_pages: int = 3

    def key(self) -> str:
        parts = [f"{k}={v}" for k, v in asdict(self).items() if v not in (None, "") and k != "max_pages"]
        return "&".join(parts) or "all"


@dataclass
class RawListing:
    source: str
    source_id: str
    url: str
    title: str = ""
    make_raw: str | None = None
    model_raw: str | None = None
    trim: str | None = None
    price_eur: int | None = None
    price_type: str = "asking"
    mileage_km: int | None = None
    first_registration: date | None = None
    year: int | None = None
    fuel_raw: str | None = None
    transmission_raw: str | None = None
    body_raw: str | None = None
    power_kw: int | None = None
    engine_cc: int | None = None
    battery_kwh: float | None = None
    doors: int | None = None
    seats: int | None = None
    colour_raw: str | None = None
    kenteken: str | None = None
    seller_type: str | None = None  # dealer | private
    seller_name: str | None = None
    seller_bovag: bool = False
    warranty_months: int | None = None
    postcode: str | None = None
    city: str | None = None
    lat: float | None = None
    lon: float | None = None
    image_urls: list[str] = field(default_factory=list)
    description: str = ""
    options_raw: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)
    is_demo: bool = False


class SourceBlocked(Exception):
    """The site refused us (403/429/captcha). The pipeline backs off and reports it."""


class SourceAdapter(Protocol):
    name: str
    label: str
    verified: bool

    def search(self, query: SourceQuery) -> Iterator[RawListing]: ...

    def detail(self, url_or_id: str) -> RawListing | None: ...

    def supports_url(self, url: str) -> bool: ...


class PoliteClient:
    """httpx client with a per-source minimum delay between requests and backoff on refusals."""

    def __init__(self, delay_s: float | None = None, client: httpx.Client | None = None):
        settings = get_settings()
        self.delay_s = settings.crawl_request_delay_s if delay_s is None else delay_s
        self._last = 0.0
        self.client = client or httpx.Client(
            headers={
                "User-Agent": settings.user_agent,
                "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.6",
            },
            timeout=20.0,
            follow_redirects=True,
        )

    def get(self, url: str, **kwargs) -> httpx.Response:
        wait = self.delay_s - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        resp = self.client.get(url, **kwargs)
        if resp.status_code in (403, 429):
            raise SourceBlocked(f"{resp.status_code} from {httpx.URL(url).host}")
        # A tiny HTML page mentioning a captcha is a challenge page, not content.
        if len(resp.content) < 20_000 and "captcha" in resp.text.lower():
            raise SourceBlocked(f"captcha challenge from {httpx.URL(url).host}")
        resp.raise_for_status()
        return resp
