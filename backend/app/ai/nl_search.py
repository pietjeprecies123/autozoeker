"""Natural-language search → structured filters.

A rule-based Dutch parser always runs (works offline, no API key). When Claude is configured, it is
used instead for richer interpretation, constrained to our filter schema and canonical slugs.
"""

from __future__ import annotations

import json
import re

from app.ai.client import AiRefused, get_client, request_kwargs, text_of
from app.config import get_settings
from app.normalize.fields import OPTION_PATTERNS
from app.normalize.taxonomy import _match_model, find_make, load_taxonomy
from app.search import SearchFilters


def _money(s: str) -> int:
    s = s.lower().replace("€", "").replace(" ", "")
    mult = 1000 if s.endswith("k") or "duizend" in s else 1
    digits = re.sub(r"[^\d,.]", "", s.rstrip("k"))
    if not digits:
        return 0
    if "," in digits and "." not in digits and len(digits.split(",")[-1]) != 3:
        value = float(digits.replace(",", "."))
    else:
        value = float(digits.replace(".", "").replace(",", ""))
    return int(value * mult)


def rule_based(text: str) -> tuple[SearchFilters, list[str]]:
    t = text.lower()
    f = SearchFilters()
    notes: list[str] = []

    amount = r"(\d[\d.,]*(?<![.,])(?![\d.,])\s*(?:k(?!m)|duizend)?)"
    m = re.search(r"(?:onder|max(?:imaal)?|tot|<|beneden|hooguit|budget(?: van)?)\s*(?:de\s*)?€?\s*" + amount
                  + r"(?:\s*(?:euro|eur))?(?!\s*(?:km|kilometer|kg|jaar|kw|pk))", t)
    if m:
        f.price_max = _money(m.group(1))
    m = re.search(r"(?:vanaf|boven|min(?:imaal)?)\s*€\s*" + amount, t)
    if m:
        f.price_min = _money(m.group(1))
    m = re.search(r"(?:onder|max(?:imaal)?|tot|minder dan)\s*" + amount + r"\s*(?:km|kilometer)", t)
    if m:
        f.km_max = _money(m.group(1))
    m = re.search(r"(?:vanaf|na|nieuwer dan|jonger dan)\s*(?:bouwjaar\s*)?(20\d\d|19\d\d)", t)
    if m:
        f.year_min = int(m.group(1))
    m = re.search(r"(?:niet ouder dan|max(?:imaal)?)\s*(\d{1,2})\s*jaar", t)
    if m:
        from app.util import today

        f.year_min = today().year - int(m.group(1))
    m = re.search(r"(\d{3,4})\s*kg", t)
    if m and re.search(r"trek|caravan|aanhang", t):
        f.towing_min = int(m.group(1))
    elif re.search(r"caravan", t):
        f.towing_min = 1200
        notes.append("Caravan → trekgewicht minimaal 1.200 kg aangenomen")
    m = re.search(r"(\d{3})\s*km\s*(?:actieradius|range|bereik)|(?:actieradius|range|bereik)\s*(?:van\s*)?(?:minimaal\s*)?(\d{3})", t)
    if m:
        f.range_min = int(m.group(1) or m.group(2))
    m = re.search(r"(?:binnen|max(?:imaal)?)\s*(\d{1,3})\s*km\s*(?:rijden|van huis|afstand|bij mij)", t)
    if m:
        f.max_distance_km = int(m.group(1))

    fuels = []
    if re.search(r"plug[\s-]?in|phev", t):
        fuels.append("plugin_hybride")
    elif re.search(r"hybride|hybrid", t):
        fuels.append("hybride")
    if re.search(r"elektrisch|\bev\b|\bbev\b|stekker", t):
        fuels.append("elektrisch")
    if "diesel" in t:
        fuels.append("diesel")
    if re.search(r"benzine", t):
        fuels.append("benzine")
    if "lpg" in t:
        fuels.append("lpg")
    if re.search(r"zuinig", t) and not fuels:
        fuels = ["hybride", "elektrisch", "plugin_hybride"]
        notes.append("Zuinig → hybride, plug-in of elektrisch")
    f.fuels = fuels

    if re.search(r"automaat|automatisch|\bdsg\b|\bcvt\b", t):
        f.transmissions = ["automaat"]
    elif re.search(r"handgeschakeld|handbak|schakel", t):
        f.transmissions = ["handgeschakeld"]

    bodies = []
    for word, body in (("stationwagen", "stationwagen"), ("station", "stationwagen"), ("combi", "stationwagen"),
                       ("suv", "suv"), ("crossover", "suv"), ("hatchback", "hatchback"), ("sedan", "sedan"),
                       ("mpv", "mpv"), ("cabrio", "cabrio"), ("coup", "coupe")):
        if word in t and body not in bodies:
            bodies.append(body)
    if re.search(r"gezin|kinderen|kinderwagen", t) and not bodies:
        bodies = ["stationwagen", "suv", "mpv"]
        notes.append("Gezinsauto → stationwagen, SUV of MPV")
    if re.search(r"7[\s-]?(zits|persoons|plaats)", t):
        f.seats_min = 7
        if not bodies:
            bodies = ["mpv", "suv"]
    if re.search(r"stad|klein|compact", t) and not bodies:
        bodies = ["hatchback"]
    f.bodies = bodies

    f.options = [opt for opt, pat in OPTION_PATTERNS.items() if re.search(pat, t) and opt != "trekhaak_afneembaar"]
    if "trekhaak" in f.options and f.towing_min is None and re.search(r"caravan|aanhang", t):
        f.towing_min = 1200

    if re.search(r"bovag", t):
        f.bovag_only = True
    if re.search(r"garantie", t):
        f.warranty_only = True
    if re.search(r"dealer", t):
        f.seller_types = ["dealer"]
    elif re.search(r"particulier", t):
        f.seller_types = ["private"]
    if re.search(r"geen import", t):
        f.hide_import = True

    make = find_make(text)
    if make:
        mk = load_taxonomy()[make]
        cleaned = mk._pattern.sub(" ", text) if mk._pattern else text
        found = _match_model(mk, cleaned)
        if found:
            f.models = [f"{make}/{found[0].slug}"]
        else:
            f.makes = [make]
    else:
        hit = _model_without_make(text)
        if hit:
            f.models = [hit]
            notes.append(f"Model herkend zonder merk: {hit}")
    return f, notes


def _model_without_make(text: str) -> str | None:
    """'golf variant' → volkswagen/golf. Only distinctive aliases (4+ characters) to avoid false hits."""
    best: tuple[int, int, str] | None = None
    for mk in load_taxonomy().values():
        for md in mk.models.values():
            for pattern, alias in md._patterns:
                if len(alias) < 4 or alias.startswith("re:") or alias.isdigit():
                    continue
                m = pattern.search(text)
                if m:
                    key = (m.start(), -len(m.group(0)), f"{mk.slug}/{md.slug}")
                    if best is None or key < best:
                        best = key
    return best[2] if best else None


def _catalog_brief() -> str:
    parts = []
    for mk in load_taxonomy().values():
        parts.append(f"{mk.slug}: " + ", ".join(md.slug for md in mk.models.values()))
    return "\n".join(parts)


FILTER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["filters", "explanation", "sort"],
    "properties": {
        "explanation": {"type": "string"},
        "sort": {"type": "string", "enum": ["best", "deal", "price_asc", "km", "newest", "distance", "year"]},
        "filters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["makes", "models", "fuels", "bodies", "transmissions", "options", "price_min", "price_max",
                         "km_max", "year_min", "seats_min", "towing_min", "range_min", "max_distance_km",
                         "seller_types", "bovag_only", "warranty_only", "hide_import"],
            "properties": {
                "makes": {"type": "array", "items": {"type": "string"}},
                "models": {"type": "array", "items": {"type": "string"}, "description": "make/model slugs"},
                "fuels": {"type": "array", "items": {"type": "string", "enum": [
                    "benzine", "diesel", "elektrisch", "hybride", "plugin_hybride", "lpg"]}},
                "bodies": {"type": "array", "items": {"type": "string", "enum": [
                    "hatchback", "sedan", "stationwagen", "suv", "mpv", "coupe", "cabrio"]}},
                "transmissions": {"type": "array", "items": {"type": "string", "enum": ["handgeschakeld", "automaat"]}},
                "options": {"type": "array", "items": {"type": "string", "enum": sorted(OPTION_PATTERNS)}},
                "price_min": {"type": ["integer", "null"]},
                "price_max": {"type": ["integer", "null"]},
                "km_max": {"type": ["integer", "null"]},
                "year_min": {"type": ["integer", "null"]},
                "seats_min": {"type": ["integer", "null"]},
                "towing_min": {"type": ["integer", "null"]},
                "range_min": {"type": ["integer", "null"]},
                "max_distance_km": {"type": ["integer", "null"]},
                "seller_types": {"type": "array", "items": {"type": "string", "enum": ["dealer", "private"]}},
                "bovag_only": {"type": "boolean"},
                "warranty_only": {"type": "boolean"},
                "hide_import": {"type": "boolean"},
            },
        },
    },
}


def with_claude(text: str, client=None) -> tuple[SearchFilters, str, str]:
    settings = get_settings()
    client = client or get_client()
    model_id = settings.claude_model
    response = client.beta.messages.create(
        model=model_id,
        max_tokens=4000,
        system=(
            "Je vertaalt een zoekvraag naar een tweedehands auto in Nederland naar zoekfilters. Gebruik alleen "
            "merk- en model-slugs uit deze lijst (formaat merk/model voor models):\n" + _catalog_brief() +
            "\nKies bij vage wensen (gezinsauto, zuinig, stadsauto) passende carrosserieën/brandstoffen en leg in "
            "'explanation' (Nederlands, 1-3 zinnen) uit welke aannames je deed. Laat velden leeg/null als de "
            "gebruiker er niets over zegt. Bedragen in hele euro's."
        ),
        messages=[{"role": "user", "content": text}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": FILTER_SCHEMA}},
        **request_kwargs(model_id),
    )
    if response.stop_reason == "refusal":
        raise AiRefused("Claude weigerde dit verzoek")
    data = json.loads(text_of(response))
    valid_models = {f"{mk.slug}/{md.slug}" for mk in load_taxonomy().values() for md in mk.models.values()}
    raw = data["filters"]
    raw["models"] = [m for m in raw.get("models", []) if m in valid_models]
    raw["makes"] = [m for m in raw.get("makes", []) if m in load_taxonomy()]
    filters = SearchFilters(**{k: v for k, v in raw.items() if v not in (None, [], False)})
    return filters, data.get("explanation", ""), data.get("sort", "best")
