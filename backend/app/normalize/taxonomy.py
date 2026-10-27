"""Canonical make/model/generation lookup backed by taxonomy.yaml."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

TAXONOMY_PATH = Path(__file__).with_name("taxonomy.yaml")


@dataclass(frozen=True)
class Generation:
    id: str
    name: str
    year_from: int
    year_to: int | None
    keywords: tuple[str, ...] = ()

    def covers(self, year: int) -> bool:
        return self.year_from <= year and (self.year_to is None or year <= self.year_to)


@dataclass
class ModelDef:
    slug: str
    name: str
    make: str
    segment: str
    body: str | None
    fuel: str | None
    aliases: list[str]
    hints: dict[str, dict]
    generations: list[Generation]
    _patterns: list[tuple[re.Pattern, str]] = field(default_factory=list, repr=False)


@dataclass
class MakeDef:
    slug: str
    name: str
    aliases: list[str]
    models: dict[str, ModelDef]
    _pattern: re.Pattern | None = None


@dataclass
class ModelMatch:
    make: str
    model: str | None
    generation: str | None
    body_hint: str | None = None
    fuel_hint: str | None = None


def _alias_pattern(alias: str) -> re.Pattern:
    if alias.startswith("re:"):
        return re.compile(alias[3:], re.I)
    escaped = re.escape(alias.lower()).replace(r"\ ", r"[\s\-]?")
    return re.compile(rf"(?<![\w.]){escaped}(?![\w])", re.I)


@lru_cache
def load_taxonomy() -> dict[str, MakeDef]:
    raw = yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))
    makes: dict[str, MakeDef] = {}
    for m in raw["makes"]:
        models: dict[str, ModelDef] = {}
        for md in m["models"]:
            gens = [
                Generation(
                    id=g["id"],
                    name=g["name"],
                    year_from=int(g["from"]),
                    year_to=int(g["to"]) if g.get("to") else None,
                    keywords=tuple(k.lower() for k in g.get("keywords", [])),
                )
                for g in md.get("generations", [])
            ]
            model = ModelDef(
                slug=str(md["slug"]),
                name=str(md["name"]),
                make=m["slug"],
                segment=md.get("segment", "C"),
                body=md.get("body"),
                fuel=md.get("fuel"),
                aliases=[str(a) for a in md.get("aliases", [])] or [str(md["slug"])],
                hints={k.lower(): v for k, v in (md.get("hints") or {}).items()},
                generations=gens,
            )
            model._patterns = [(_alias_pattern(a), a.lower()) for a in model.aliases]
            models[model.slug] = model
        make = MakeDef(slug=m["slug"], name=m["name"], aliases=[str(a) for a in m["aliases"]], models=models)
        alts = sorted({a.lower() for a in make.aliases}, key=len, reverse=True)
        make._pattern = re.compile(
            r"(?<![\w])(" + "|".join(re.escape(a).replace(r"\ ", r"[\s\-]?") for a in alts) + r")(?![\w])", re.I
        )
        makes[make.slug] = make
    return makes


def find_make(text: str | None) -> str | None:
    if not text:
        return None
    best: tuple[int, int, str] | None = None
    for make in load_taxonomy().values():
        assert make._pattern is not None
        m = make._pattern.search(text)
        if m:
            key = (m.start(), -len(m.group(0)), make.slug)
            if best is None or key < best:
                best = key
    return best[2] if best else None


def _match_model(make: MakeDef, text: str) -> tuple[ModelDef, str] | None:
    best: tuple[int, int, ModelDef, str] | None = None
    for model in make.models.values():
        for pattern, alias in model._patterns:
            m = pattern.search(text)
            if m:
                key = (m.start(), -len(m.group(0)))
                if best is None or key < best[:2]:
                    best = (key[0], key[1], model, alias)
    return (best[2], best[3]) if best else None


def pick_generation(model: ModelDef, year: int | None, text: str = "") -> str | None:
    if not model.generations:
        return None
    lowered = f" {text.lower()} "
    for gen in model.generations:
        for kw in gen.keywords:
            if re.search(rf"(?<![\w]){re.escape(kw)}(?![\w])", lowered):
                return gen.id
    if year is None:
        return model.generations[-1].id if len(model.generations) == 1 else None
    candidates = [g for g in model.generations if g.covers(year)]
    if candidates:
        return max(candidates, key=lambda g: g.year_from).id
    # outside known ranges: nearest generation
    return min(model.generations, key=lambda g: abs(g.year_from - year)).id


def match_vehicle(
    make_raw: str | None, model_raw: str | None, title: str | None = None, year: int | None = None
) -> ModelMatch | None:
    taxonomy = load_taxonomy()
    make_slug = find_make(make_raw) or find_make(title) or find_make(model_raw)
    if not make_slug:
        return None
    make = taxonomy[make_slug]
    found: tuple[ModelDef, str] | None = None
    # The model field is matched as-is; in the title we strip the first make mention only, so a model
    # that shares its name with the make ("MINI Mini", "smart #1") still matches.
    for text, strip in ((model_raw, False), (title, True)):
        if not text:
            continue
        cleaned = make._pattern.sub(" ", text, count=1) if (strip and make._pattern) else text
        found = _match_model(make, cleaned.strip())
        if found:
            break
    if not found:
        return ModelMatch(make=make_slug, model=None, generation=None)
    model, alias = found
    hint = model.hints.get(alias, {})
    context = " ".join(t for t in (model_raw, title) if t)
    return ModelMatch(
        make=make_slug,
        model=model.slug,
        generation=pick_generation(model, year, context),
        body_hint=hint.get("body") or model.body,
        fuel_hint=hint.get("fuel") or model.fuel,
    )


def get_model(make: str | None, model: str | None) -> ModelDef | None:
    if not make or not model:
        return None
    mk = load_taxonomy().get(make)
    return mk.models.get(model) if mk else None


def display_name(make: str | None, model: str | None = None) -> str:
    if not make:
        return "Onbekend"
    mk = load_taxonomy().get(make)
    if not mk:
        return make
    if not model:
        return mk.name
    md = mk.models.get(model)
    return f"{mk.name} {md.name if md else model}"


def generation_name(make: str | None, model: str | None, generation: str | None) -> str | None:
    md = get_model(make, model)
    if not md or not generation:
        return None
    for g in md.generations:
        if g.id == generation:
            return g.name
    return None


def catalog() -> list[dict]:
    """Serializable make/model/generation tree for the UI."""
    out = []
    for mk in sorted(load_taxonomy().values(), key=lambda m: m.name.lower()):
        out.append(
            {
                "slug": mk.slug,
                "name": mk.name,
                "models": [
                    {
                        "slug": md.slug,
                        "name": md.name,
                        "segment": md.segment,
                        "generations": [
                            {"id": g.id, "name": g.name, "from": g.year_from, "to": g.year_to}
                            for g in md.generations
                        ],
                    }
                    for md in sorted(mk.models.values(), key=lambda m: m.name.lower())
                ],
            }
        )
    return out
