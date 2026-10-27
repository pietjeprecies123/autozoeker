"""Map free-text attribute values from listing sites and RDW to canonical values."""

from __future__ import annotations

import re

FUELS = ["benzine", "diesel", "elektrisch", "hybride", "plugin_hybride", "lpg", "cng", "waterstof"]
FUEL_LABELS = {
    "benzine": "Benzine",
    "diesel": "Diesel",
    "elektrisch": "Elektrisch",
    "hybride": "Hybride",
    "plugin_hybride": "Plug-in hybride",
    "lpg": "LPG",
    "cng": "Aardgas (CNG)",
    "waterstof": "Waterstof",
}
TRANSMISSIONS = ["handgeschakeld", "automaat"]
BODIES = ["hatchback", "sedan", "stationwagen", "suv", "mpv", "coupe", "cabrio", "bestelwagen", "pickup"]
BODY_LABELS = {
    "hatchback": "Hatchback",
    "sedan": "Sedan",
    "stationwagen": "Stationwagen",
    "suv": "SUV / Crossover",
    "mpv": "MPV",
    "coupe": "Coupé",
    "cabrio": "Cabrio",
    "bestelwagen": "Bestelwagen",
    "pickup": "Pick-up",
}


def norm_fuel(raw: str | None, text: str = "") -> str | None:
    s = f"{raw or ''}".lower()
    t = f"{s} {text.lower()}"
    if not s and not text:
        return None
    if re.search(r"plug[\s-]?in|phev|\bphv\b|extern oplaadbaar", t):
        return "plugin_hybride"
    if "waterstof" in s or "hydrogen" in s:
        return "waterstof"
    if re.search(r"\blpg\b|autogas", s):
        return "lpg"
    if re.search(r"\bcng\b|aardgas", s):
        return "cng"
    if re.search(r"hybri|\bhev\b|e:hev|full hybrid|mild", s) or ("elektr" in s and ("benz" in s or "dies" in s)):
        return "hybride"
    if re.search(r"elektr|electric|\bev\b|\bbev\b", s):
        return "elektrisch"
    if "diesel" in s:
        return "diesel"
    if re.search(r"benzine|petrol|gasoline|\bbenz", s):
        return "benzine"
    if not s:
        # derive from title only when no raw value
        if re.search(r"\bhybrid", t):
            return "hybride"
        if re.search(r"\b(tdi|cdi|dci|crdi|hdi|bluehdi|d4|d3|d5|tdci|multijet|jtd)\b", t):
            return "diesel"
        if re.search(r"\b(tsi|tfsi|tce|puretech|ecoboost|gdi|t-gdi|vti|mpi|skyactiv-g)\b", t):
            return "benzine"
    return None


def norm_transmission(raw: str | None, text: str = "") -> str | None:
    s = f"{raw or ''} {text}".lower()
    if not s.strip():
        return None
    if re.search(r"automa|automatic|\bdsg\b|\bcvt\b|\bdct\b|\bedc\b|tiptronic|steptronic|s[\s-]?tronic|e-cvt|\bat\b|\beat\d", s):
        return "automaat"
    if re.search(r"handgeschakeld|handmatig|manual|schakel|\bmt\b|\b[56]-?bak|\bhandbak", s):
        return "handgeschakeld"
    return None


def norm_body(raw: str | None, text: str = "") -> str | None:
    s = f"{raw or ''}".lower()
    t = f"{s} {text.lower()}"
    if not t.strip():
        return None
    rules = [
        ("stationwagen", r"station|combi|estate|touring|variant|sportswagen|\bsw\b|avant|sports tourer|break|kombi|wagon|shooting brake|sportstourer|\bst\b"),
        ("suv", r"\bsuv\b|terrein|crossover|offroad|off-road|4x4"),
        ("mpv", r"\bmpv\b|monovolume|ruimtewagen|people carrier"),
        ("cabrio", r"cabrio|convertible|roadster|spider|spyder"),
        ("coupe", r"coup[eé]"),
        ("sedan", r"sedan|limousine|saloon|berline"),
        ("bestelwagen", r"bestel|\bvan\b|gesloten bus"),
        ("pickup", r"pick[\s-]?up"),
        ("hatchback", r"hatchback|hatch|\b[35][\s-]?d(eurs|rs)?\b|sportback"),
    ]
    for target in (s, t):
        for body, pattern in rules:
            if re.search(pattern, target):
                return body
    return None


COLOURS = {
    "zwart": ["zwart", "black", "schwarz"],
    "wit": ["wit", "white", "weiss", "weiß", "parelmoer"],
    "grijs": ["grijs", "grey", "gray", "antraciet", "grau"],
    "zilver": ["zilver", "silver", "silber"],
    "blauw": ["blauw", "blue", "blau"],
    "rood": ["rood", "red", "rot", "bordeaux"],
    "groen": ["groen", "green", "grün"],
    "geel": ["geel", "yellow", "gelb"],
    "oranje": ["oranje", "orange"],
    "bruin": ["bruin", "brown", "braun", "beige", "brons"],
    "paars": ["paars", "purple", "violet"],
}


def norm_colour(raw: str | None) -> str | None:
    if not raw:
        return None
    s = raw.lower()
    for colour, words in COLOURS.items():
        if any(w in s for w in words):
            return colour
    return None


OPTION_PATTERNS: dict[str, str] = {
    "trekhaak": r"trekhaak|tow ?bar|anh[aä]ngerkupplung|afneembare haak",
    "navigatie": r"navigatie|navi\b|navigation|gps",
    "climate_control": r"climate control|klimaatregeling|ecc\b|clima",
    "airco": r"airco|air conditioning",
    "cruise_control": r"cruise control|cruise\b",
    "adaptive_cruise": r"adaptive cruise|adaptieve cruise|\bacc\b",
    "stoelverwarming": r"stoelverwarming|seat heating|heated seats",
    "warmtepomp": r"warmtepomp|heat ?pump",
    "panoramadak": r"panorama|schuifdak|open dak|sunroof",
    "leder": r"leder|leather|leer\b",
    "camera": r"camera",
    "parkeersensoren": r"parkeersensor|pdc|park distance|parkeerhulp",
    "apple_carplay": r"carplay|android auto",
    "led": r"\bled\b|matrix",
    "keyless": r"keyless",
    "trekhaak_afneembaar": r"afneembare trekhaak",
    "dakrails": r"dakrails|roof rails",
    "lichtmetalen_velgen": r"lichtmetalen|lm velgen|alloy",
    "head_up": r"head[\s-]?up",
    "isofix": r"isofix",
}
OPTION_LABELS = {
    "trekhaak": "Trekhaak",
    "navigatie": "Navigatie",
    "climate_control": "Climate control",
    "airco": "Airco",
    "cruise_control": "Cruise control",
    "adaptive_cruise": "Adaptieve cruise control",
    "stoelverwarming": "Stoelverwarming",
    "warmtepomp": "Warmtepomp",
    "panoramadak": "Panoramadak",
    "leder": "Leder",
    "camera": "Camera",
    "parkeersensoren": "Parkeersensoren",
    "apple_carplay": "Apple CarPlay / Android Auto",
    "led": "LED-verlichting",
    "keyless": "Keyless",
    "trekhaak_afneembaar": "Afneembare trekhaak",
    "dakrails": "Dakrails",
    "lichtmetalen_velgen": "Lichtmetalen velgen",
    "head_up": "Head-up display",
    "isofix": "Isofix",
}


def extract_options(*texts: str | None) -> list[str]:
    blob = " ".join(t for t in texts if t).lower()
    found = [opt for opt, pat in OPTION_PATTERNS.items() if re.search(pat, blob)]
    if "trekhaak_afneembaar" in found and "trekhaak" not in found:
        found.append("trekhaak")
    return sorted(set(found))


def extract_power_kw(text: str | None) -> int | None:
    if not text:
        return None
    t = text.lower()
    m = re.search(r"(\d{2,3})\s?kw\b", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d{2,3})\s?(pk|ps|hp)\b", t)
    if m:
        return int(round(int(m.group(1)) * 0.7355))
    return None


def extract_battery_kwh(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"(\d{2,3}(?:[.,]\d)?)\s?kwh", text.lower())
    if m:
        value = float(m.group(1).replace(",", "."))
        if 10 <= value <= 150:
            return value
    return None


def extract_engine_cc(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"(?<![\d.])([0-6])[.,]([0-9])\s?(?:l\b|liter|tsi|tfsi|tdi|tce|puretech|ecoboost|turbo|gdi|t-gdi|vvt|vti|mpi|hybrid|d\b|i\b|e-thp|thp|dci|crdi|hdi|bluehdi|multijet|skyactiv)", text.lower())
    if m:
        litres = float(f"{m.group(1)}.{m.group(2)}")
        if 0.6 <= litres <= 6.5:
            # nominal displacement (e.g. "1.2" → 1200); knowledge-base rules match on ranges
            return int(round(litres * 1000))
    return None
