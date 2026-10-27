"""Adapter parsers against ASSUMED page shapes.

These fixtures are hand-written from the expected structure (no live access during development).
Replace them with real captures (`autozoeker capture <source>`) once verified on a machine that can
reach the sites; until then the adapters are marked verified=False in the UI.
"""

import json

from app.sources import autoscout24, marktplaats
from app.sources.base import SourceQuery

AS24_ITEM = {
    "id": "c0ffee-1",
    "url": "/aanbod/volkswagen-golf-1-5-tsi-life-benzine-grijs-c0ffee-1",
    "images": ["https://img/1.jpg"],
    "price": {"priceFormatted": "€ 21.950,-"},
    "vehicle": {"make": "Volkswagen", "model": "Golf", "modelVersionInput": "1.5 TSI Life", "mileageInKm": "45.000 km",
                "fuel": "Benzine", "transmission": "Handgeschakeld"},
    "location": {"countryCode": "NL", "zip": "3511 AB", "city": "Utrecht"},
    "seller": {"type": "Dealer", "companyName": "Autobedrijf X"},
    "tracking": {"firstRegistration": "06-2021", "mileage": "45000", "price": "21950"},
    "vehicleDetails": [{"data": "110 kW (150 PK)", "iconName": "speedometer"}],
}


def as24_html(items):
    data = {"props": {"pageProps": {"listings": items}}}
    return f'<html><body><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></body></html>'


def test_as24_parse_search():
    items = autoscout24.parse_search(as24_html([AS24_ITEM]))
    assert len(items) == 1
    it = items[0]
    assert it.price_eur == 21950 and it.mileage_km == 45000 and it.power_kw == 110
    assert it.first_registration.year == 2021 and it.postcode == "3511" and it.seller_type == "dealer"
    assert it.url.startswith("https://www.autoscout24.nl/aanbod/")


def test_as24_finds_listings_at_other_paths_and_skips_foreign():
    nested = {"props": {"pageProps": {"search": {"results": [AS24_ITEM, dict(AS24_ITEM, id="c2", location={"countryCode": "DE"})]}}}}
    html = f'<script id="__NEXT_DATA__">{json.dumps(nested)}</script>'
    items = autoscout24.parse_search(html)
    assert [i.source_id for i in items] == ["c0ffee-1"]


def test_as24_search_url():
    url = autoscout24.search_url(SourceQuery(make="volkswagen", model="id-3", price_max=30000, fuel="elektrisch"), 2)
    assert "/lst/volkswagen/id.3" in url and "priceto=30000" in url and "fuel=E" in url and "page=2" in url


MP_PAYLOAD = {
    "totalResultCount": 1,
    "listings": [{
        "itemId": "m2012345678",
        "title": "Toyota Yaris 1.5 Hybrid Active | NAP | Kenteken RX-123-B",
        "description": "Nette auto",
        "priceInfo": {"priceCents": 1495000, "priceType": "FIXED"},
        "location": {"cityName": "Amersfoort", "countryCode": "NL", "latitude": 52.15, "longitude": 5.38},
        "pictures": [{"largeUrl": "https://img/mp.jpg"}],
        "sellerInformation": {"sellerName": "Jan", "showWebsiteUrl": False},
        "vipUrl": "/v/auto-s/toyota/m2012345678-toyota-yaris",
        "attributes": [{"key": "constructionYear", "value": "2021"}, {"key": "mileage", "value": "54.321"},
                       {"key": "fuel", "value": "Hybride"}, {"key": "transmission", "value": "Automaat"},
                       {"key": "brand", "value": "Toyota"}, {"key": "model", "value": "Yaris"}],
    }],
}


def test_marktplaats_parse():
    items = marktplaats.parse_search(MP_PAYLOAD)
    it = items[0]
    assert it.price_eur == 14950 and it.mileage_km == 54321 and it.year == 2021 and it.seller_type == "private"
    assert it.url.startswith("https://www.marktplaats.nl/v/") and it.lat == 52.15
    from app.normalize import normalize_raw

    f = normalize_raw(it)
    assert f["make"] == "toyota" and f["model"] == "yaris" and f["kenteken"] is None  # title plates are not trusted


def test_marktplaats_search_url():
    url = marktplaats.search_url(SourceQuery(make="toyota", model="yaris", price_max=15000, km_max=100000), 0)
    assert "l1CategoryId=91" in url and "query=Toyota+Yaris" in url and "PriceCents%3A0%3A1500000" in url
