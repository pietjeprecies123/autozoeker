"""Known model-specific issues ("aandachtspunten").

Curated YAML files in app/knowledge/issues/ describe issues per model or per engine family. This
module loads them, matches them to a listing (make/model/generation/year/fuel/engine) and checks the
car's RDW recall history to tell whether a recall-type issue has been repaired.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.models import Listing, Vehicle

ISSUES_DIR = Path(__file__).with_name("issues")

SEVERITY_COST = {"low": 300, "medium": 1200, "high": 3500, "critical": 7000}
LIKELIHOOD = {"low": 0.08, "medium": 0.25, "high": 0.5}
CERTAINTY_FACTOR = {"zeker": 1.0, "waarschijnlijk": 0.8, "mogelijk": 0.5}
SEVERITY_LABEL = {"low": "Laag", "medium": "Middel", "high": "Hoog", "critical": "Kritiek"}
_ENGINE_TEXT = re.compile(
    r"\b\d[.,]\d\b|\b(tsi|tfsi|tdi|tce|dci|puretech|bluehdi|ecoboost|t-gdi|gdi|crdi|cdti|vvt-i|skyactiv|"
    r"dig-t|ig-t|mpi|multijet|twinair|e-thp|hybrid|phev|kwh)\b",
    re.I,
)


@dataclass
class IssueMatch:
    issue: dict
    file_id: str
    certainty: str  # zeker | waarschijnlijk | mogelijk
    recall_status: str | None = None  # open | hersteld | None
    recall_refs: list[str] | None = None

    @property
    def expected_cost(self) -> float:
        lo, hi = self.issue.get("repair_cost_eur") or [None, None]
        mid = (lo + hi) / 2 if lo is not None and hi is not None else SEVERITY_COST.get(self.issue.get("severity", "medium"), 1000)
        p = LIKELIHOOD.get(self.issue.get("likelihood", "medium"), 0.25)
        factor = CERTAINTY_FACTOR.get(self.certainty, 0.5)
        if self.recall_status == "hersteld":
            factor *= 0.1
        elif self.recall_status == "open":
            factor = 1.0  # confirmed affected, repair still to be done (usually free at the dealer)
            mid = min(mid, 150)  # recall repairs are free; residual cost is your time
        return mid * p * factor

    def to_dict(self) -> dict:
        d = dict(self.issue)
        d["file_id"] = self.file_id
        d["certainty"] = self.certainty
        d["recall_status"] = self.recall_status
        d["recall_refs"] = self.recall_refs or []
        d["severity_label"] = SEVERITY_LABEL.get(d.get("severity", "medium"), d.get("severity"))
        d["expected_cost_eur"] = int(round(self.expected_cost))
        return d


@lru_cache
def load_files() -> list[dict]:
    files = []
    for path in sorted(ISSUES_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        data.setdefault("id", path.stem)
        data["_path"] = path.name
        files.append(data)
    return files


# AI-researched files (from the issue_research table), used only for models without curated files
_ai_files: dict[tuple[str, str], dict] = {}


def set_ai_files(files: list[dict]) -> None:
    _ai_files.clear()
    for f in files:
        for target in f.get("applies_to", []):
            _ai_files[(target.get("make"), target.get("model"))] = f


def load_ai_files(session) -> None:
    from sqlalchemy import select

    from app.models import IssueResearch

    set_ai_files([r.result for r in session.scalars(select(IssueResearch)) if r.result])


def curated_files_for(make: str | None, model: str | None) -> list[dict]:
    out = []
    for f in load_files():
        for target in f.get("applies_to", []):
            if target.get("make") == make and (target.get("model") in (None, model)):
                out.append(f)
                break
    return out


def files_for(make: str | None, model: str | None) -> list[dict]:
    curated = curated_files_for(make, model)
    model_specific = [f for f in curated if any(t.get("model") == model for t in f.get("applies_to", []))]
    if not model_specific and (make, model) in _ai_files:
        return curated + [_ai_files[(make, model)]]
    return curated


def _in_range(value: int | None, rng) -> bool | None:
    if not rng:
        return True
    if value is None:
        return None
    lo, hi = rng[0], rng[1] if len(rng) > 1 else None
    return (lo is None or value >= lo) and (hi is None or value <= hi)


def _applies_to_model(f: dict, issue: dict, make: str | None, model: str | None) -> bool:
    targets = issue.get("applies_to") or f.get("applies_to") or []
    return any(t.get("make") == make and t.get("model") in (None, model) for t in targets)


def match_issue(f: dict, issue: dict, listing: Listing) -> str | None:
    """Return certainty or None if the issue does not apply to this car."""
    if not _applies_to_model(f, issue, listing.make, listing.model):
        return None
    uncertain = False
    gens = issue.get("generations")
    if gens:
        if listing.generation is None:
            uncertain = True
        elif listing.generation not in gens:
            return None
    year = listing.first_registration.year if listing.first_registration else listing.year
    yr = _in_range(year, issue.get("years"))
    if yr is False:
        return None
    if yr is None:
        uncertain = True
    fuels = issue.get("fuels")
    if fuels:
        if listing.fuel is None:
            uncertain = True
        elif listing.fuel not in fuels:
            return None

    engine = issue.get("engine")
    if engine:
        text = f"{listing.title or ''} {listing.trim or ''}".lower()
        keywords = [k.lower() for k in engine.get("keywords", [])]
        exclude = [k.lower() for k in engine.get("exclude_keywords", [])]
        if exclude and any(re.search(rf"(?<![\w]){re.escape(k)}(?![\w])", text) for k in exclude):
            return None
        kw_hit = any(re.search(rf"(?<![\w]){re.escape(k)}(?![\w])", text) for k in keywords) if keywords else False
        cc_ok = _in_range(listing.engine_cc, engine.get("cc"))
        kw_ok = _in_range(listing.power_kw, engine.get("kw"))
        if kw_hit and cc_ok is not False and kw_ok is not False:
            return "mogelijk" if uncertain else "zeker"
        if engine.get("cc") and cc_ok and kw_ok is not False:
            return "waarschijnlijk"
        engine_known = listing.engine_cc is not None or _ENGINE_TEXT.search(text)
        if engine_known:
            # the advert names its engine and it is not this one
            return None
        return "mogelijk"
    return "mogelijk" if uncertain else "zeker"


def _recall_state(issue: dict, vehicle: Vehicle | None) -> tuple[str | None, list[str]]:
    fix = issue.get("fix") or {}
    keywords = [k.lower() for k in fix.get("rdw_recall_keywords", [])]
    if not vehicle or not vehicle.recalls or not keywords:
        return None, []
    hits = []
    for rc in vehicle.recalls:
        blob = " ".join(str(rc.get(k) or "") for k in ("omschrijving_defect", "gevolgen", "herstel", "titel")).lower()
        if any(k in blob for k in keywords):
            hits.append(rc)
    if not hits:
        return None, []
    refs = [h.get("referentiecode_rdw") for h in hits if h.get("referentiecode_rdw")]
    if any(h.get("open") for h in hits):
        return "open", refs
    return "hersteld", refs


def issues_for(listing: Listing, vehicle: Vehicle | None = None) -> list[IssueMatch]:
    matches: list[IssueMatch] = []
    for f in files_for(listing.make, listing.model):
        for issue in f.get("issues", []):
            certainty = match_issue(f, issue, listing)
            if not certainty:
                continue
            state, refs = _recall_state(issue, vehicle)
            matches.append(IssueMatch(issue=issue, file_id=f["id"], certainty=certainty, recall_status=state, recall_refs=refs))
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    matches.sort(key=lambda m: (order.get(m.issue.get("severity", "medium"), 2), -m.expected_cost))
    return matches


def risk(listing: Listing, vehicle: Vehicle | None = None) -> tuple[float, int, int]:
    """(score 0..1, expected repair cost €, number of matching issues)."""
    matches = issues_for(listing, vehicle)
    cost = sum(m.expected_cost for m in matches)
    score = max(0.0, min(1.0, 1 - cost / 3000))
    return score, int(round(cost)), len(matches)


def model_overview(make: str, model: str) -> dict | None:
    fs = files_for(make, model)
    if not fs:
        return None
    issues = []
    for f in fs:
        for issue in f.get("issues", []):
            if _applies_to_model(f, issue, make, model):
                issues.append(dict(issue, file_id=f["id"], severity_label=SEVERITY_LABEL.get(issue.get("severity", "medium"))))
    main = next((f for f in fs if any(t.get("model") == model for t in f.get("applies_to", []))), fs[0])
    return {
        "files": [{"id": f["id"], "title": f.get("title"), "summary": f.get("summary"), "source": f.get("source", "curated")}
                  for f in fs],
        "title": main.get("title"),
        "summary": main.get("summary"),
        "battery_warranty": next((f.get("battery_warranty") for f in fs if f.get("battery_warranty")), None),
        "general_checks": [c for f in fs for c in f.get("general_checks", [])],
        "issues": issues,
        "source": main.get("source", "curated"),
        "has_model_specific": any(any(t.get("model") == model for t in f.get("applies_to", [])) for f in fs),
    }


def coverage() -> list[dict]:
    """Which make/models the curated base covers (for the UI and to decide on AI research)."""
    out = []
    for f in load_files():
        out.append({
            "id": f["id"],
            "title": f.get("title"),
            "applies_to": f.get("applies_to", []),
            "n_issues": len(f.get("issues", [])),
            "reviewed": max((str(i.get("reviewed", "")) for i in f.get("issues", [])), default=""),
        })
    return out
