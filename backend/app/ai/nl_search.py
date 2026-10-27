"""Natural-language search → structured filters.

A rule-based Dutch parser always runs (works offline, no API key). When Claude is configured, it is
used instead for richer interpretation, constrained to our filter schema and canonical slugs.
"""

from __future__ import annotations

import json
import re

from app.ai.client import AiRefused, get_client, request_kwargs, text_of
from app.config import get_settings
from app.normalize.fields import FUELS, OPTION_PATTERNS
from app.normalize.taxonomy import _match_model, find_make, load_taxonomy
from app.search import SearchFilters
from app.util import negated


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


# A number with an optional thousands word and unit: "15k", "20 duizend", "€12.500", "100.000 km", "1500 kg"
_AMOUNT = (r"(?P<num>\d[\d.,]*(?<![.,]))(?![\d.,])(?P<mult>\s*(?:k\b|duizend))?(?:\s*(?:euro|eur)\b)?"
           r"(?P<unit>\s*(?:km|kilometer|kg|kilo|jaar|kw|pk|bouwjaar|zits|persoons)\b)?")


def _first_amount(t: str, prefix: str, units: tuple[str, ...] = ()) -> int | None:
    """First amount after `prefix` with one of `units` (no units = a price, i.e. no unit at all)."""
    for m in re.finditer(prefix + r"\s*(?:de\s*)?€?\s*" + _AMOUNT, t):
        unit = (m.group("unit") or "").strip()
        if (unit in units) if units else not unit:
            return _money(m.group("num") + (m.group("mult") or ""))
    return None


def _said(pattern: str, t: str) -> tuple[bool, bool]:
    """(asked for, ruled out): 'geen diesel' rules diesel out instead of asking for it."""
    asked = ruled_out = False
    for m in re.finditer(pattern, t):
        if negated(t, m.start()):
            ruled_out = True
        else:
            asked = True
    return asked, ruled_out


def rule_based(text: str) -> tuple[SearchFilters, list[str]]:
    t = text.lower()
    f = SearchFilters()
    notes: list[str] = []

    f.price_max = _first_amount(t, r"(?:onder|max(?:imaal)?|tot|<|beneden|hooguit|budget(?: van)?)")
    f.price_min = _first_amount(t, r"(?:vanaf|boven|min(?:imaal)?)\s*€")
    f.km_max = _first_amount(t, r"(?:onder|max(?:imaal)?|tot|minder dan)", ("km", "kilometer"))
    m = re.search(r"(?:vanaf|na|nieuwer dan|jonger dan)\s*(?:bouwjaar\s*)?(20\d\d|19\d\d)", t)
    if m:
        f.year_min = int(m.group(1))
    m = re.search(r"(?:tot|t/m|max(?:imaal)?)\s*(?:bouwjaar\s*(20\d\d|19\d\d)|(20\d\d|19\d\d)\s*bouwjaar)", t)
    if m:
        f.year_max = int(m.group(1) or m.group(2))
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

    wanted: list[str] = []
    excluded: list[str] = []
    # "plug-in hybride" is a plug-in, not also a plain hybrid
    without_plugin = re.sub(r"plug[\s-]?in[\s-]*(?:hybride|hybrid)?|phev", " ", t)
    for fuel, pattern, text_ in (
        ("plugin_hybride", r"plug[\s-]?in|phev", t),
        ("hybride", r"hybride|hybrid", without_plugin),
        ("elektrisch", r"elektrisch|\bev\b|\bbev\b|stekker", t),
        ("diesel", r"diesel", t),
        ("benzine", r"benzine", t),
        ("lpg", r"\blpg\b", t),
    ):
        asked, ruled_out = _said(pattern, text_)
        if asked:
            wanted.append(fuel)
        elif ruled_out:
            excluded.append(fuel)
    if wanted:
        f.fuels = wanted
    elif re.search(r"zuinig", t):
        f.fuels = [x for x in ("hybride", "elektrisch", "plugin_hybride") if x not in excluded]
        notes.append("Zuinig → hybride, plug-in of elektrisch")
    elif excluded:
        f.fuels = [x for x in FUELS if x not in excluded]
        notes.append("Geen " + " of ".join(excluded) + " → alle andere brandstoffen")

    auto_asked, auto_out = _said(r"automaat|automatisch|\bdsg\b|\bcvt\b", t)
    manual_asked, manual_out = _said(r"handgeschakeld|handbak|schakel", t)
    if auto_asked or (manual_out and not manual_asked):
        f.transmissions = ["automaat"]
    elif manual_asked or auto_out:
        f.transmissions = ["handgeschakeld"]

    bodies = []
    for word, body in (("stationwagen", "stationwagen"), ("station", "stationwagen"), ("combi", "stationwagen"),
                       ("suv", "suv"), ("crossover", "suv"), ("hatchback", "hatchback"), ("sedan", "sedan"),
                       ("mpv", "mpv"), ("cabrio", "cabrio"), ("coup", "coupe")):
        if _said(re.escape(word), t)[0] and body not in bodies:
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

    f.options = [opt for opt, pat in OPTION_PATTERNS.items() if _said(pat, t)[0] and opt != "trekhaak_afneembaar"]
    if "trekhaak" in f.options and f.towing_min is None and re.search(r"caravan|aanhang", t):
        f.towing_min = 1200

    if _said(r"bovag", t)[0]:
        f.bovag_only = True
    if _said(r"garantie", t)[0]:
        f.warranty_only = True
    if _said(r"dealer", t)[0]:
        f.seller_types = ["dealer"]
    elif _said(r"particulier", t)[0]:
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
