"""Postcode → coordinates, and distances.

Primary source is the PDOK Locatieserver (free Dutch government geocoder), cached per PC4 in the
database. Offline, or when PDOK is unreachable, we fall back to an approximate centroid per PC2
region (first two digits), which is accurate to roughly 10–25 km — good enough to filter by distance.
"""

from __future__ import annotations

import logging
import math
import re
import time

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AppSetting

log = logging.getLogger(__name__)

# Approximate centroid of each PC2 region (main town in brackets).
PC2_CENTROIDS: dict[str, tuple[float, float]] = {
    "10": (52.372, 4.894),  # Amsterdam
    "11": (52.310, 4.900),  # Amsterdam-Zuidoost / Amstelveen / Diemen
    "12": (52.223, 5.176),  # Hilversum / Het Gooi
    "13": (52.371, 5.222),  # Almere
    "14": (52.503, 4.959),  # Purmerend / Waterland
    "15": (52.439, 4.826),  # Zaanstad
    "16": (52.642, 5.060),  # Hoorn / West-Friesland
    "17": (52.760, 4.860),  # Heerhugowaard / Schagen / Den Helder
    "18": (52.632, 4.749),  # Alkmaar
    "19": (52.484, 4.656),  # Beverwijk / IJmond
    "20": (52.381, 4.637),  # Haarlem
    "21": (52.302, 4.690),  # Haarlemmermeer / Heemstede
    "22": (52.230, 4.480),  # Duin- en Bollenstreek
    "23": (52.160, 4.497),  # Leiden
    "24": (52.129, 4.657),  # Alphen aan den Rijn
    "25": (52.070, 4.300),  # Den Haag
    "26": (52.005, 4.330),  # Delft / Rijswijk / Westland
    "27": (52.058, 4.494),  # Zoetermeer
    "28": (52.012, 4.711),  # Gouda
    "29": (51.900, 4.600),  # Capelle / Krimpen / Ridderkerk
    "30": (51.922, 4.479),  # Rotterdam
    "31": (51.915, 4.350),  # Schiedam / Vlaardingen / Maassluis
    "32": (51.845, 4.250),  # Spijkenisse / Voorne-Putten
    "33": (51.813, 4.669),  # Dordrecht
    "34": (52.040, 5.020),  # Woerden / Nieuwegein / IJsselstein
    "35": (52.090, 5.121),  # Utrecht
    "36": (52.150, 5.010),  # Maarssen / Breukelen
    "37": (52.110, 5.250),  # Zeist / De Bilt / Soest
    "38": (52.156, 5.387),  # Amersfoort
    "39": (52.027, 5.558),  # Veenendaal / Rhenen
    "40": (51.887, 5.430),  # Tiel
    "41": (51.930, 5.200),  # Culemborg / Leerdam
    "42": (51.834, 4.974),  # Gorinchem
    "43": (51.500, 3.610),  # Middelburg / Vlissingen
    "44": (51.504, 3.889),  # Goes
    "45": (51.335, 3.828),  # Terneuzen / Zeeuws-Vlaanderen
    "46": (51.495, 4.288),  # Bergen op Zoom
    "47": (51.531, 4.465),  # Roosendaal
    "48": (51.589, 4.776),  # Breda
    "49": (51.645, 4.860),  # Oosterhout
    "50": (51.560, 5.091),  # Tilburg
    "51": (51.660, 5.030),  # Waalwijk / Dongen
    "52": (51.698, 5.304),  # 's-Hertogenbosch
    "53": (51.765, 5.520),  # Oss / Zaltbommel
    "54": (51.657, 5.620),  # Uden / Veghel
    "55": (51.390, 5.440),  # Veldhoven / Valkenswaard
    "56": (51.441, 5.478),  # Eindhoven
    "57": (51.481, 5.656),  # Helmond
    "58": (51.580, 5.950),  # Venray / Boxmeer
    "59": (51.370, 6.170),  # Venlo
    "60": (51.220, 5.900),  # Roermond / Weert
    "61": (51.000, 5.870),  # Sittard-Geleen
    "62": (50.851, 5.691),  # Maastricht
    "63": (50.870, 5.830),  # Valkenburg / Meerssen
    "64": (50.885, 6.000),  # Heerlen / Kerkrade
    "65": (51.842, 5.853),  # Nijmegen
    "66": (51.860, 5.700),  # Wijchen / Druten / Elst
    "67": (52.030, 5.660),  # Ede / Wageningen
    "68": (51.985, 5.899),  # Arnhem
    "69": (51.930, 6.070),  # Zevenaar / Duiven
    "70": (51.965, 6.289),  # Doetinchem
    "71": (51.970, 6.650),  # Winterswijk / Aalten
    "72": (52.140, 6.200),  # Zutphen / Lochem
    "73": (52.211, 5.970),  # Apeldoorn
    "74": (52.255, 6.163),  # Deventer
    "75": (52.221, 6.894),  # Enschede / Hengelo
    "76": (52.357, 6.660),  # Almelo
    "77": (52.575, 6.620),  # Hardenberg / Ommen
    "78": (52.785, 6.897),  # Emmen
    "79": (52.720, 6.480),  # Hoogeveen / Meppel
    "80": (52.512, 6.091),  # Zwolle
    "81": (52.400, 6.200),  # Raalte / Salland
    "82": (52.518, 5.471),  # Lelystad / Kampen
    "83": (52.710, 5.750),  # Emmeloord / Steenwijk
    "84": (52.960, 5.920),  # Heerenveen
    "85": (52.965, 5.790),  # Joure / Lemmer
    "86": (53.033, 5.660),  # Sneek
    "87": (53.050, 5.450),  # Bolsward / Workum
    "88": (53.175, 5.420),  # Franeker / Harlingen
    "89": (53.201, 5.799),  # Leeuwarden
    "90": (53.150, 5.850),  # Grou e.o.
    "91": (53.326, 5.998),  # Dokkum
    "92": (53.107, 6.098),  # Drachten
    "93": (53.140, 6.430),  # Roden / Leek
    "94": (52.993, 6.562),  # Assen
    "95": (52.990, 6.950),  # Stadskanaal
    "96": (53.160, 6.860),  # Hoogezand / Veendam
    "97": (53.219, 6.566),  # Groningen
    "98": (53.250, 6.400),  # Zuidhorn
    "99": (53.320, 6.890),  # Delfzijl / Appingedam
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def road_km(straight_km: float) -> float:
    """Rough road distance: Dutch roads average ~1.25× the straight line."""
    return straight_km * 1.25


def pc4(postcode: str | None) -> str | None:
    if not postcode:
        return None
    m = re.match(r"\s*(\d{4})", postcode)
    return m.group(1) if m else None


def pc2_centroid(postcode: str | None) -> tuple[float, float] | None:
    code = pc4(postcode)
    return PC2_CENTROIDS.get(code[:2]) if code else None


_pdok_down_until = 0.0


def _pdok_lookup(code: str) -> tuple[float, float] | None:
    global _pdok_down_until
    if time.monotonic() < _pdok_down_until:
        return None
    settings = get_settings()
    try:
        return _pdok_request(settings.pdok_url, code)
    except Exception:
        # circuit breaker: don't hammer (or wait on) an unreachable service for every listing
        _pdok_down_until = time.monotonic() + 600
        raise


def _pdok_request(url: str, code: str) -> tuple[float, float] | None:
    resp = httpx.get(
        url,
        params={"q": f"postcode:{code}*", "fq": "type:postcode", "rows": 1, "fl": "centroide_ll"},
        timeout=8.0,
    )
    resp.raise_for_status()
    docs = resp.json().get("response", {}).get("docs", [])
    if not docs:
        return None
    m = re.match(r"POINT\(([\d.]+) ([\d.]+)\)", docs[0].get("centroide_ll", ""))
    if not m:
        return None
    return float(m.group(2)), float(m.group(1))


def geocode(session: Session | None, postcode: str | None) -> tuple[float, float, bool] | None:
    """Returns (lat, lon, precise). precise=False means PC2 approximation."""
    code = pc4(postcode)
    if not code:
        return None
    key = f"geo:{code}"
    if session is not None:
        cached = session.get(AppSetting, key)
        if cached and isinstance(cached.value, list):
            return cached.value[0], cached.value[1], True
    settings = get_settings()
    if settings.online_enrichment:
        try:
            found = _pdok_lookup(code)
        except Exception as exc:  # network blocked/offline: fall back silently
            log.debug("PDOK lookup failed for %s: %s", code, exc)
            found = None
        if found:
            if session is not None:
                session.merge(AppSetting(key=key, value=[found[0], found[1]]))
            return found[0], found[1], True
    approx = pc2_centroid(code)
    return (approx[0], approx[1], False) if approx else None
