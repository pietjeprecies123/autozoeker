"""Negotiation helper: suggested opening bid, a walk-away price, and the arguments to use."""

from __future__ import annotations

from app.models import Listing, Vehicle
from app.util import euro, today, utcnow


def advise(listing: Listing, vehicle: Vehicle | None, issue_matches: list, comparables: list[Listing]) -> dict | None:
    price = listing.price_eur
    if not price:
        return None
    market = listing.predicted_price or price
    low = listing.predicted_low or int(market * 0.9)
    args: list[str] = []
    leverage = 0.03 if listing.seller_type == "dealer" else 0.05

    if listing.predicted_price:
        diff = price - market
        if diff > 0:
            args.append(f"De vraagprijs ligt {euro(diff)} boven onze marktschatting ({euro(market)}).")
            leverage += min(0.05, diff / price)
        else:
            args.append(f"De vraagprijs ligt {euro(-diff)} onder de marktschatting; veel ruimte is er niet, wees redelijk.")

    days = (utcnow() - listing.first_seen_at).days if listing.first_seen_at else 0
    if days > 60:
        leverage += 0.04
        args.append(f"De auto staat al {days} dagen te koop.")
    elif days > 30:
        leverage += 0.02
        args.append(f"De auto staat al {days} dagen online.")

    drops = max(0, len(listing.prices or []) - 1)
    if drops:
        leverage += min(0.03, 0.01 * drops)
        args.append(f"De prijs is al {drops}× verlaagd: de verkoper wil verkopen.")

    cheaper = [c for c in comparables if c.price_eur and c.price_eur < price and c.status == "active"]
    if cheaper:
        best = min(cheaper, key=lambda c: c.price_eur)
        args.append(f"Er staan {len(cheaper)} vergelijkbare auto's goedkoper te koop (vanaf {euro(best.price_eur)}).")

    repair = 0
    for m in issue_matches:
        if m.recall_status == "hersteld":
            continue
        lo, hi = m.issue.get("repair_cost_eur") or [0, 0]
        if m.certainty == "zeker" and m.issue.get("likelihood") in ("medium", "high") and hi:
            repair += int((lo + hi) / 2 * 0.5)
            args.append(f"Bekend aandachtspunt: {m.issue.get('title')} (reparatie {euro(lo)}–{euro(hi)}); vraag bewijs van herstel of verreken het risico.")
    if vehicle and vehicle.apk_expiry and (vehicle.apk_expiry - today()).days < 90:
        repair += 150
        args.append("APK verloopt binnen 3 maanden: vraag om nieuwe APK bij aflevering of verreken ~€150.")
    if vehicle and vehicle.open_recall:
        args.append("Er staat een terugroepactie open: laat die vóór aflevering uitvoeren (kosteloos).")
    if listing.mileage_km and listing.expected_km and listing.mileage_km > listing.expected_km * 1.3:
        args.append("Bovengemiddeld veel kilometers voor de leeftijd: slijtagedelen (remmen, banden, koppeling) zijn eerder aan de beurt.")
    if listing.seller_type == "dealer" and not listing.warranty_months:
        args.append("Geen garantie vermeld: vraag om (BOVAG-)garantie of een lagere prijs.")

    leverage = min(leverage, 0.15)
    # floor to tens so the suggestions never end up above the asking price through rounding
    opening = int(min(price, market) * (1 - leverage) - repair * 0.5) // 10 * 10
    walk_away = int(min(price, max(low, market * 1.02) - repair)) // 10 * 10
    opening = min(opening, walk_away)
    return {
        "asking": price,
        "market": market,
        "opening_bid": max(0, opening),
        "walk_away": max(0, walk_away),
        "expected_repairs": repair,
        "arguments": args,
        "tips": [
            "Bied niet meteen je maximum; laat de verkoper eerst zakken.",
            "Onderhandel ook over extra's: nieuwe APK, beurt, banden, garantie of een volle tank/laadpas.",
            "Bij een dealer is inruil vaak de sleutel: vraag de prijs zonder en met inruil apart.",
            "Laat een aankoopkeuring (ANWB/BOVAG, ca. €150–250) uitvoeren voordat je tekent.",
        ],
    }
