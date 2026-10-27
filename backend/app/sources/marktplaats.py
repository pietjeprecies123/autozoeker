"""Marktplaats adapter (category 91 = Auto's).

STATUS: UNVERIFIED. Uses the JSON endpoint the Marktplaats web front-end itself calls
(/lrp/api/search), with field names as used by community tools, without live access from the
development environment. Verify on your own machine with `autozoeker verify-sources`; capture raw
responses with `autozoeker capture marktplaats` if the parser needs fixing.

Seller type is heuristic (dealers usually expose a website/company profile). Many dealer adverts
mention the kenteken in the text; we extract it when written as a plate (AB-123-C) or labelled.

Terms of use: Marktplaats prohibits automated collection in its terms. Keep this to low-volume personal
use or disable the source.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from urllib.parse import urlencode

from app.normalize.taxonomy import display_name, get_model
from app.sources.base import PoliteClient, RawListing, SourceQuery
from app.util import parse_date, parse_int

BASE = "https://www.marktplaats.nl"
API = f"{BASE}/lrp/api/search"
PAGE_SIZE = 100


def query_text(q: SourceQuery) -> str:
    if q.text:
        return q.text
    if q.make and q.model:
        md = get_model(q.make, q.model)
        return f"{display_name(q.make)} {md.name if md else q.model}"
    if q.make:
        return display_name(q.make)
    return ""


def search_url(q: SourceQuery, offset: int) -> str:
    params: list[tuple[str, str]] = [
        ("l1CategoryId", "91"),
        ("limit", str(PAGE_SIZE)),
        ("offset", str(offset)),
        ("sortBy", "SORT_INDEX"),
        ("sortOrder", "DECREASING"),
        ("viewOptions", "list-view"),
    ]
    text = query_text(q)
    if text:
        params.append(("query", text))
    if q.price_min or q.price_max:
        lo = (q.price_min or 0) * 100
        hi = (q.price_max * 100) if q.price_max else ""
        params.append(("attributeRanges[]", f"PriceCents:{lo}:{hi}"))
    if q.year_min:
        params.append(("attributeRanges[]", f"constructionYear:{q.year_min}:"))
    if q.km_max:
        params.append(("attributeRanges[]", f"mileage:0:{q.km_max}"))
    return f"{API}?{urlencode(params)}"


def _attrs(item: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for a in item.get("attributes") or []:
        if isinstance(a, dict) and a.get("key"):
            out[str(a["key"])] = str(a.get("value") or "")
    for a in item.get("extendedAttributes") or []:
        if isinstance(a, dict) and a.get("key") and str(a["key"]) not in out:
            out[str(a["key"])] = str(a.get("value") or "")
    return out


def _image(item: dict) -> list[str]:
    urls = []
    for p in item.get("pictures") or []:
        if isinstance(p, dict):
            u = p.get("largeUrl") or p.get("mediumUrl") or p.get("extraExtraLargeUrl")
            if u:
                urls.append(u)
    for u in item.get("imageUrls") or []:
        if isinstance(u, str):
            urls.append("https:" + u if u.startswith("//") else u)
    return urls


def parse_item(item: dict) -> RawListing | None:
    item_id = item.get("itemId")
    if not item_id:
        return None
    a = _attrs(item)
    price_info = item.get("priceInfo") or {}
    cents = price_info.get("priceCents")
    price_type = str(price_info.get("priceType") or "FIXED").upper()
    price = int(cents) // 100 if isinstance(cents, (int, float)) and cents else None
    ptype = "asking" if price_type in ("FIXED", "FAST_BID", "MIN_BID") else ("bidding" if "BID" in price_type else "on_request")
    if price_type == "MIN_BID":
        ptype = "bidding"
    loc = item.get("location") or {}
    seller = item.get("sellerInformation") or {}
    dealer = bool(seller.get("showWebsiteUrl") or seller.get("sellerWebsiteUrl") or seller.get("isDealer"))
    url = item.get("vipUrl") or ""
    if url.startswith("/"):
        url = BASE + url
    year = parse_int(a.get("constructionYear"))
    reg = parse_date(a.get("registrationDate") or a.get("firstRegistrationDate")) or (parse_date(str(year)) if year else None)
    title = str(item.get("title") or "")
    description = str(item.get("description") or item.get("categorySpecificDescription") or "")
    lat, lon = loc.get("latitude"), loc.get("longitude")
    return RawListing(
        source="marktplaats",
        source_id=str(item_id),
        url=url,
        title=title,
        make_raw=a.get("brand") or None,
        model_raw=a.get("model") or None,
        trim=None,
        price_eur=price,
        price_type=ptype,
        mileage_km=parse_int(a.get("mileage")),
        first_registration=reg,
        year=year,
        fuel_raw=a.get("fuel"),
        transmission_raw=a.get("transmission"),
        body_raw=a.get("body"),
        power_kw=parse_int(re.sub(r"[^\d]", "", a.get("powerKw", "") or a.get("enginePower", "")) or None),
        engine_cc=parse_int(a.get("engineDisplacement")),
        doors=parse_int(a.get("numberOfDoors")),
        seats=parse_int(a.get("numberOfSeats")),
        colour_raw=a.get("color") or a.get("colour"),
        kenteken=a.get("licensePlate") or a.get("kenteken"),
        seller_type="dealer" if dealer else "private",
        seller_name=seller.get("sellerName"),
        postcode=None,
        city=loc.get("cityName"),
        lat=float(lat) if isinstance(lat, (int, float)) and lat else None,
        lon=float(lon) if isinstance(lon, (int, float)) and lon else None,
        image_urls=_image(item),
        description=description,
        options_raw=[v for k, v in a.items() if k == "options"],
        extra={"priority": item.get("priorityProduct"), "attributes": a},
    )


def parse_search(payload: dict) -> list[RawListing]:
    out = []
    for item in payload.get("listings") or []:
        parsed = parse_item(item)
        if parsed:
            out.append(parsed)
    return out


class MarktplaatsAdapter:
    name = "marktplaats"
    label = "Marktplaats"
    verified = False

    def __init__(self, client: PoliteClient | None = None):
        self.client = client or PoliteClient()

    def supports_url(self, url: str) -> bool:
        return "marktplaats.nl" in url

    def search(self, query: SourceQuery) -> Iterator[RawListing]:
        for page in range(max(1, query.max_pages)):
            payload = self.client.get(search_url(query, page * PAGE_SIZE), headers={"Accept": "application/json"}).json()
            items = parse_search(payload)
            yield from items
            total = payload.get("totalResultCount") or 0
            if len(items) < PAGE_SIZE or (page + 1) * PAGE_SIZE >= total:
                break

    def detail(self, url_or_id: str) -> RawListing | None:
        """Detail pages are HTML; we re-find the advert through the search API by its item id."""
        m = re.search(r"(m\d{9,})", url_or_id)
        if not m:
            return None
        payload = self.client.get(f"{API}?{urlencode({'l1CategoryId': '91', 'query': m.group(1), 'limit': '10'})}").json()
        for item in parse_search(payload):
            if item.source_id == m.group(1):
                return item
        return None
