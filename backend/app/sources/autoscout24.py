"""AutoScout24.nl adapter.

STATUS: UNVERIFIED. Written against AutoScout24's Next.js page structure (a JSON blob in
<script id="__NEXT_DATA__">) as publicly documented by community scrapers, without live access from the
development environment. Run `autozoeker verify-sources` (or `make verify-sources`) on your own machine;
if parsing fails, `autozoeker capture autoscout24` saves raw pages under captures/ so the parser can be
fixed against real data.

The parser is defensive: it looks for listing-like objects anywhere in the page JSON rather than at one
fixed path, so small layout changes don't break it.

Terms of use: AutoScout24 does not offer a public consumer API and its terms restrict automated access.
This adapter is meant for low-volume personal use (one request per few seconds, only the searches you save).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from urllib.parse import urlencode

from selectolax.lexbor import LexborHTMLParser

from app.sources.base import PoliteClient, RawListing, SourceQuery
from app.util import parse_date, parse_int

BASE = "https://www.autoscout24.nl"

# AutoScout24 fuel codes (query parameter `fuel`)
FUEL_CODES = {"benzine": "B", "diesel": "D", "elektrisch": "E", "hybride": "2", "plugin_hybride": "2", "lpg": "L", "cng": "C", "waterstof": "H"}

# URL slugs that differ from our canonical slugs (extend when verify-sources reports misses)
MAKE_SLUGS = {"mercedes-benz": "mercedes-benz", "land-rover": "land-rover", "lynk-co": "lynk-&-co", "citroen": "citroen"}
MODEL_SLUGS: dict[tuple[str, str], str] = {
    ("volkswagen", "id-3"): "id.3",
    ("volkswagen", "id-4"): "id.4",
    ("volkswagen", "id-5"): "id.5",
    ("bmw", "1-serie"): "1-series",
    ("bmw", "2-serie-active-tourer"): "2-series-active-tourer",
    ("bmw", "3-serie"): "3-series",
    ("bmw", "5-serie"): "5-series",
    ("mercedes-benz", "a-klasse"): "a-class",
    ("mercedes-benz", "b-klasse"): "b-class",
    ("mercedes-benz", "c-klasse"): "c-class",
    ("mercedes-benz", "e-klasse"): "e-class",
    ("tesla", "model-3"): "model-3",
    ("tesla", "model-y"): "model-y",
    ("mazda", "2"): "2",
    ("mazda", "3"): "3",
}


def search_url(q: SourceQuery, page: int) -> str:
    path = "/lst"
    if q.make:
        path += "/" + MAKE_SLUGS.get(q.make, q.make)
        if q.model:
            path += "/" + MODEL_SLUGS.get((q.make, q.model), q.model)
    params: dict = {"atype": "C", "cy": "NL", "desc": "1", "sort": "age", "ustate": "N,U", "page": page,
                    "damaged_listing": "exclude", "powertype": "kw"}
    if q.price_min:
        params["pricefrom"] = q.price_min
    if q.price_max:
        params["priceto"] = q.price_max
    if q.km_max:
        params["kmto"] = q.km_max
    if q.year_min:
        params["fregfrom"] = q.year_min
    if q.fuel and q.fuel in FUEL_CODES:
        params["fuel"] = FUEL_CODES[q.fuel]
    return f"{BASE}{path}?{urlencode(params)}"


def next_data(html: str) -> dict | None:
    tree = LexborHTMLParser(html)
    node = tree.css_first("script#__NEXT_DATA__")
    if node is None:
        return None
    try:
        return json.loads(node.text())
    except json.JSONDecodeError:
        return None


def _walk(obj, found: list[dict]) -> None:
    if isinstance(obj, dict):
        if ("vehicle" in obj and ("price" in obj or "tracking" in obj)) and ("id" in obj or "url" in obj):
            found.append(obj)
            return
        for v in obj.values():
            _walk(v, found)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, found)


def find_listings(data: dict) -> list[dict]:
    try:
        direct = data["props"]["pageProps"]["listings"]
        if isinstance(direct, list) and direct:
            return direct
    except (KeyError, TypeError):
        pass
    found: list[dict] = []
    _walk(data, found)
    return found


def _details_text(item: dict) -> list[str]:
    out = []
    for d in item.get("vehicleDetails") or []:
        if isinstance(d, dict) and d.get("data"):
            out.append(str(d["data"]))
    return out


def parse_item(item: dict) -> RawListing | None:
    vehicle = item.get("vehicle") or {}
    tracking = item.get("tracking") or {}
    price_obj = item.get("price") or {}
    source_id = str(item.get("id") or "")
    url = item.get("url") or ""
    if url and url.startswith("/"):
        url = BASE + url
    if not source_id and not url:
        return None
    details = _details_text(item)
    price = parse_int(tracking.get("price")) or parse_int(price_obj.get("priceFormatted") if isinstance(price_obj, dict) else price_obj)
    km = parse_int(tracking.get("mileage")) or parse_int(vehicle.get("mileageInKm"))
    reg = parse_date(tracking.get("firstRegistration")) or parse_date(vehicle.get("firstRegistrationDate"))
    kw = None
    for d in details:
        m = re.search(r"(\d{2,3})\s*kW", d)
        if m:
            kw = int(m.group(1))
        if reg is None and re.fullmatch(r"\d{2}/\d{4}", d.strip()):
            reg = parse_date(d.strip())
        if km is None and "km" in d:
            km = parse_int(d)
    location = item.get("location") or {}
    seller = item.get("seller") or {}
    seller_type = str(seller.get("type") or "").lower()
    images = item.get("images") or []
    images = [i if isinstance(i, str) else (i.get("url") if isinstance(i, dict) else None) for i in images]
    title = " ".join(x for x in (vehicle.get("make"), vehicle.get("model"), vehicle.get("modelVersionInput")) if x)
    if location.get("countryCode") and str(location.get("countryCode")).upper() != "NL":
        return None
    return RawListing(
        source="autoscout24",
        source_id=source_id or url,
        url=url,
        title=title or str(item.get("title") or ""),
        make_raw=vehicle.get("make"),
        model_raw=vehicle.get("model"),
        trim=vehicle.get("modelVersionInput"),
        price_eur=price,
        mileage_km=km,
        first_registration=reg,
        fuel_raw=vehicle.get("fuel") or tracking.get("fuelType"),
        transmission_raw=vehicle.get("transmission"),
        power_kw=kw,
        seller_type="dealer" if "dealer" in seller_type else ("private" if seller_type else None),
        seller_name=seller.get("companyName") or seller.get("contactName"),
        postcode=(str(location.get("zip") or "")[:4]) or None,
        city=location.get("city"),
        image_urls=[i for i in images if i],
        extra={"details": details},
    )


def parse_search(html: str) -> list[RawListing]:
    data = next_data(html)
    if not data:
        return []
    out = []
    for item in find_listings(data):
        parsed = parse_item(item)
        if parsed:
            out.append(parsed)
    return out


def parse_detail(html: str, url: str) -> RawListing | None:
    data = next_data(html)
    if not data:
        return None
    page = (data.get("props") or {}).get("pageProps") or {}
    det = page.get("listingDetails") or {}
    if not det:
        items = find_listings(data)
        return parse_item(items[0]) if items else None
    v = det.get("vehicle") or {}
    prices = det.get("prices") or {}
    public = prices.get("public") or {}
    loc = det.get("location") or {}
    seller = det.get("seller") or {}
    raw = RawListing(
        source="autoscout24",
        source_id=str(det.get("id") or url),
        url=url,
        title=" ".join(x for x in (v.get("make"), v.get("model"), v.get("modelVersionInput")) if x),
        make_raw=v.get("make"),
        model_raw=v.get("model"),
        trim=v.get("modelVersionInput"),
        price_eur=parse_int(public.get("priceRaw") or public.get("price")),
        mileage_km=parse_int(v.get("mileageInKmRaw") or v.get("mileageInKm")),
        first_registration=parse_date(v.get("firstRegistrationDateRaw") or v.get("firstRegistrationDate")),
        fuel_raw=(v.get("fuelCategory") or {}).get("formatted") if isinstance(v.get("fuelCategory"), dict) else v.get("fuel"),
        transmission_raw=(v.get("transmissionType") or v.get("transmission")),
        body_raw=(v.get("bodyType") or ""),
        power_kw=parse_int(v.get("powerInKw") or v.get("rawPowerInKw")),
        seats=parse_int(v.get("numberOfSeats")),
        doors=parse_int(v.get("numberOfDoors")),
        colour_raw=v.get("bodyColor") or v.get("paintType"),
        kenteken=v.get("licensePlate") or v.get("registrationNumber"),
        seller_type="dealer" if "dealer" in str(seller.get("type", "")).lower() else "private",
        seller_name=seller.get("companyName"),
        postcode=(str(loc.get("zip") or "")[:4]) or None,
        city=loc.get("city"),
        image_urls=[i for i in (det.get("images") or []) if isinstance(i, str)],
        description=re.sub(r"<[^>]+>", " ", str(det.get("description") or "")),
        options_raw=[str(x) for x in (v.get("equipment") or {}).get("as24", [])] if isinstance(v.get("equipment"), dict) else [],
    )
    return raw


class AutoScout24Adapter:
    name = "autoscout24"
    label = "AutoScout24"
    verified = False

    def __init__(self, client: PoliteClient | None = None):
        self.client = client or PoliteClient()

    def supports_url(self, url: str) -> bool:
        return "autoscout24.nl" in url

    def search(self, query: SourceQuery) -> Iterator[RawListing]:
        seen: set[str] = set()
        for page in range(1, max(1, query.max_pages) + 1):
            html = self.client.get(search_url(query, page)).text
            items = parse_search(html)
            new = [i for i in items if i.source_id not in seen]
            if not new:
                break
            # everything is ingested (other models still feed the valuation); filtering happens in search
            for item in new:
                seen.add(item.source_id)
                yield item

    def detail(self, url_or_id: str) -> RawListing | None:
        url = url_or_id if url_or_id.startswith("http") else f"{BASE}/aanbod/{url_or_id}"
        html = self.client.get(url).text
        return parse_detail(html, url)

