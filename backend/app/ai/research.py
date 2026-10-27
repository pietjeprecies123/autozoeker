"""Research known issues for a model the curated knowledge base does not cover, using Claude + web search.

The result has the same shape as a curated YAML issue file, is cached in the database for
ISSUE_RESEARCH_TTL_DAYS, and is always labelled as AI-researched in the UI with its sources.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from app.ai.client import AiRefused, Usage, get_client, request_kwargs
from app.config import get_settings
from app.models import IssueResearch
from app.normalize.taxonomy import display_name, generation_name, get_model
from app.util import utcnow

log = logging.getLogger(__name__)

_STR_LIST = {"type": "array", "items": {"type": "string"}}
_NULL_INT = {"type": ["integer", "null"]}

SUBMIT_TOOL = {
    "name": "submit_research",
    "description": "Lever het eindresultaat van het onderzoek aan. Roep dit precies één keer aan, als laatste stap.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary", "battery_warranty", "general_checks", "issues"],
        "properties": {
            "summary": {"type": "string", "description": "2-4 zinnen over de betrouwbaarheid van dit model als occasion."},
            "battery_warranty": {
                "type": ["object", "null"],
                "additionalProperties": False,
                "required": ["years", "km", "min_soh_pct", "note"],
                "properties": {"years": _NULL_INT, "km": _NULL_INT, "min_soh_pct": _NULL_INT, "note": {"type": "string"}},
            },
            "general_checks": _STR_LIST,
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "title", "severity", "likelihood", "category", "years_from", "years_to", "engine_keywords",
                        "fuels", "summary", "symptoms", "repair_cost_min", "repair_cost_max", "fix_type",
                        "fix_description", "verify", "questions", "test_drive", "sources",
                    ],
                    "properties": {
                        "title": {"type": "string"},
                        "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                        "likelihood": {"type": "string", "enum": ["low", "medium", "high"]},
                        "category": {"type": "string"},
                        "years_from": _NULL_INT,
                        "years_to": _NULL_INT,
                        "engine_keywords": _STR_LIST,
                        "fuels": {"type": "array", "items": {"type": "string", "enum": [
                            "benzine", "diesel", "elektrisch", "hybride", "plugin_hybride", "lpg"]}},
                        "summary": {"type": "string"},
                        "symptoms": _STR_LIST,
                        "repair_cost_min": _NULL_INT,
                        "repair_cost_max": _NULL_INT,
                        "fix_type": {"type": "string", "enum": [
                            "recall", "campaign", "revised_part", "software", "warranty_extension", "maintenance", "none"]},
                        "fix_description": {"type": "string"},
                        "verify": _STR_LIST,
                        "questions": _STR_LIST,
                        "test_drive": _STR_LIST,
                        "sources": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["title", "url"],
                                "properties": {"title": {"type": "string"}, "url": {"type": "string"}},
                            },
                        },
                    },
                },
            },
        },
    },
}

SYSTEM = (
    "Je bent een ervaren Nederlandse auto-expert die kopers van occasions helpt. Je onderzoekt bekende, "
    "modelspecifieke problemen met behulp van webzoekopdrachten en levert alleen feiten die je in bronnen hebt "
    "gevonden. Antwoord in het Nederlands. Geef per probleem concrete vragen die een koper aan de verkoper kan "
    "stellen om te achterhalen of het probleem al is opgelost (bijv. factuur, terugroepactie, softwareversie, "
    "vervangen onderdeel), en wat je tijdens bezichtiging/proefrit kunt controleren."
)


def research_key(make: str, model: str, generation: str | None) -> str:
    return f"{make}/{model}/{generation or '*'}"


def _prompt(make: str, model: str, generation: str | None) -> str:
    md = get_model(make, model)
    gen = generation_name(make, model, generation) if generation else None
    name = display_name(make, model)
    years = ""
    if md and generation:
        g = next((g for g in md.generations if g.id == generation), None)
        if g:
            years = f" (bouwjaren {g.year_from}–{g.year_to or 'heden'})"
    return (
        f"Onderzoek bekende problemen en aandachtspunten voor een gebruikte {name}"
        f"{' – ' + gen if gen else ''}{years}, zoals die in Nederland te koop wordt aangeboden.\n\n"
        "Zoek in betrouwbare bronnen (o.a. ANWB, AutoWeek, Autovisie, TÜV-rapport/ADAC Pannenstatistik, "
        "RDW-terugroepacties, fabrikant-campagnes, grote eigenaarsfora). Beperk je tot problemen die vaker "
        "voorkomen of duur zijn; geen algemene slijtage. Vermeld per probleem: ernst, hoe vaak het voorkomt, "
        "welke bouwjaren/motoren, symptomen, indicatieve reparatiekosten in euro's, of er een terugroepactie, "
        "campagne, garantieverlenging of verbeterd onderdeel is, hoe je controleert of het al is opgelost, "
        "vragen voor de verkoper en controles tijdens de proefrit. Gebruik alleen URL's die je daadwerkelijk "
        "hebt gevonden als bron. Als het een elektrische auto of plug-in is: geef ook de batterijgarantie "
        "(jaren, km, minimale State of Health) als je die vindt.\n\n"
        "Rond af door submit_research aan te roepen met het volledige resultaat."
    )


def to_kb(make: str, model: str, generation: str | None, data: dict) -> dict:
    """Convert the tool result into the curated knowledge-base shape."""
    issues = []
    for i, it in enumerate(data.get("issues", [])):
        issue = {
            "id": f"ai-{make}-{model}-{i}",
            "title": it["title"],
            "severity": it["severity"],
            "likelihood": it["likelihood"],
            "category": it["category"],
            "summary": it["summary"],
            "symptoms": it["symptoms"],
            "fix": {"type": it["fix_type"], "description": it["fix_description"]},
            "verify": it["verify"],
            "questions": it["questions"],
            "test_drive": it["test_drive"],
            "sources": it["sources"],
            "ai": True,
        }
        if it.get("years_from") or it.get("years_to"):
            issue["years"] = [it.get("years_from"), it.get("years_to")]
        if it.get("engine_keywords"):
            issue["engine"] = {"keywords": it["engine_keywords"]}
        if it.get("fuels"):
            issue["fuels"] = it["fuels"]
        if it.get("repair_cost_min") is not None and it.get("repair_cost_max") is not None:
            issue["repair_cost_eur"] = [it["repair_cost_min"], it["repair_cost_max"]]
        if generation:
            issue["generations"] = [generation]
        issues.append(issue)
    bw = data.get("battery_warranty")
    return {
        "id": f"ai-{make}-{model}",
        "title": display_name(make, model),
        "summary": data.get("summary"),
        "applies_to": [{"make": make, "model": model}],
        "battery_warranty": bw if bw and (bw.get("years") or bw.get("km")) else None,
        "general_checks": data.get("general_checks", []),
        "issues": issues,
        "source": "ai",
    }


def run_research(make: str, model: str, generation: str | None = None, client=None) -> tuple[dict, Usage, str]:
    settings = get_settings()
    client = client or get_client()
    model_id = settings.claude_model
    usage = Usage()
    tools = [
        {"type": "web_search_20260209", "name": "web_search", "max_uses": 8,
         "user_location": {"type": "approximate", "country": "NL", "timezone": "Europe/Amsterdam"}},
        SUBMIT_TOOL,
    ]
    messages: list[dict] = [{"role": "user", "content": _prompt(make, model, generation)}]
    nudged = False
    for _ in range(8):
        response = client.beta.messages.create(
            model=model_id,
            max_tokens=16000,
            system=SYSTEM,
            tools=tools,
            messages=messages,
            output_config={"effort": "medium"},
            **request_kwargs(model_id),
        )
        usage.add(response.usage)
        if response.stop_reason == "refusal":
            raise AiRefused("Claude weigerde dit verzoek")
        for block in response.content:
            if getattr(block, "type", "") == "tool_use" and block.name == "submit_research":
                return dict(block.input), usage, model_id
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "pause_turn":
            continue
        if response.stop_reason == "tool_use":
            # only submit_research is a client tool, and it was not called: shouldn't happen
            raise RuntimeError("Onverwachte tool-aanroep")
        if nudged:
            break
        messages.append({"role": "user", "content": "Rond nu af en roep submit_research aan met je resultaten."})
        nudged = True
    raise RuntimeError("Claude leverde geen onderzoeksresultaat aan")


def get_or_research(session: Session, make: str, model: str, generation: str | None = None,
                    force: bool = False, client=None) -> IssueResearch:
    settings = get_settings()
    key = research_key(make, model, generation)
    cached = session.get(IssueResearch, key)
    fresh = cached and cached.created_at > utcnow() - timedelta(days=settings.issue_research_ttl_days)
    if fresh and not force:
        return cached
    data, usage, model_id = run_research(make, model, generation, client=client)
    record = cached or IssueResearch(key=key, make=make, model=model, generation=generation)
    record.result = to_kb(make, model, generation, data)
    record.model_used = model_id
    record.input_tokens = usage.input_tokens
    record.output_tokens = usage.output_tokens
    record.web_searches = usage.web_searches
    record.cost_usd = usage.cost_usd(model_id) or 0.0
    record.created_at = utcnow()
    if not cached:
        session.add(record)
    session.flush()
    log.info("AI research %s: %s in / %s out tokens, %s searches, $%s", key, usage.input_tokens,
             usage.output_tokens, usage.web_searches, record.cost_usd)
    return record
