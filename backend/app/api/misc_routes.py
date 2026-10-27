"""Known issues, AI endpoints, market insights and system status/admin."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.client import AiRefused, AiUnavailable
from app.api.deps import DB, get_listing, get_vehicle
from app.api.serialize import card
from app.config import get_settings
from app.ingest.pipeline import blocked_until
from app.insights import best_deals, model_insights
from app.knowledge import service as knowledge
from app.models import (
    AlertSent,
    CrawlRun,
    IssueResearch,
    Listing,
    Profile,
    SavedSearch,
    Vehicle,
    WatchlistItem,
)
from app.normalize.taxonomy import display_name, get_model
from app.sources.registry import adapters_info
from app.valuation.model import get_model_instance

router = APIRouter(prefix="/api", tags=["misc"])


# -- known issues -----------------------------------------------------------------------------------
@router.get("/issues")
def issues_index(session: Session = DB):
    research = [
        {"key": r.key, "make": r.make, "model": r.model, "generation": r.generation, "created_at": r.created_at,
         "cost_usd": r.cost_usd, "title": display_name(r.make, r.model)}
        for r in session.scalars(select(IssueResearch).order_by(IssueResearch.created_at.desc()))
    ]
    return {"curated": knowledge.coverage(), "ai": research}


@router.get("/issues/{make}/{model}")
def issues_for_model(make: str, model: str, session: Session = DB):
    if get_model(make, model) is None:
        raise HTTPException(404, "Onbekend model")
    knowledge.load_ai_files(session)
    overview = knowledge.model_overview(make, model)
    research = session.scalar(select(IssueResearch).where(IssueResearch.make == make, IssueResearch.model == model))
    return {
        "make": make,
        "model": model,
        "title": display_name(make, model),
        "overview": overview,
        "ai_research": {"created_at": research.created_at, "cost_usd": research.cost_usd, "model": research.model_used}
        if research else None,
        "ai_available": get_settings().ai_enabled,
    }


@router.post("/issues/{make}/{model}/research")
def research_model(make: str, model: str, generation: str | None = None, force: bool = False, session: Session = DB):
    from app.ai.research import get_or_research

    if get_model(make, model) is None:
        raise HTTPException(404, "Onbekend model")
    try:
        record = get_or_research(session, make, model, generation, force=force)
    except AiUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except AiRefused as exc:
        raise HTTPException(422, str(exc)) from exc
    knowledge.load_ai_files(session)
    # rescore listings of this model so issue risk is reflected
    from app.analysis import refresh

    ids = list(session.scalars(select(Listing.id).where(Listing.make == make, Listing.model == model, Listing.status == "active")))
    refresh(session, ids)
    return {"result": record.result, "cost_usd": record.cost_usd, "web_searches": record.web_searches,
            "input_tokens": record.input_tokens, "output_tokens": record.output_tokens}


# -- AI -------------------------------------------------------------------------------------------
class NlIn(BaseModel):
    text: str


@router.post("/ai/parse-search")
def parse_search(body: NlIn):
    from app.ai import nl_search

    rule_filters, notes = nl_search.rule_based(body.text)
    if get_settings().ai_enabled:
        try:
            filters, explanation, sort = nl_search.with_claude(body.text)
            return {"filters": filters.model_dump(exclude_defaults=True), "explanation": explanation, "sort": sort,
                    "engine": "claude"}
        except Exception as exc:  # fall back to the rule-based parser
            notes.append(f"AI niet beschikbaar ({type(exc).__name__}); regels gebruikt")
    return {"filters": rule_filters.model_dump(exclude_defaults=True), "explanation": "; ".join(notes),
            "sort": "best", "engine": "rules"}


@router.post("/listings/{listing_id}/ad-scan")
def ad_scan(listing_id: int, force: bool = False, session: Session = DB):
    from app.ai import ad_scan as scan_mod

    listing = get_listing(session, listing_id)
    cached = (listing.extra or {}).get("ad_scan")
    if cached and not force:
        return cached
    try:
        result = scan_mod.scan(listing, get_vehicle(session, listing))
    except AiUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except AiRefused as exc:
        raise HTTPException(422, str(exc)) from exc
    listing.extra = {**(listing.extra or {}), "ad_scan": result}
    return result


# -- insights -------------------------------------------------------------------------------------
@router.get("/insights/deals")
def insights_deals(session: Session = DB):
    return {"items": [card(x) for x in best_deals(session)]}


@router.get("/insights/{make}")
def insights_make(make: str, model: str | None = None, fuel: str | None = None, days: int = 120, session: Session = DB):
    data = model_insights(session, make, model, fuel, days)
    deal_listings = list(session.scalars(select(Listing).where(Listing.id.in_(data.pop("deal_ids")))))
    deal_listings.sort(key=lambda x: -(x.deal_score or 0))
    data["deals"] = [card(x) for x in deal_listings]
    data["title"] = display_name(make, model)
    return data


# -- status & admin -------------------------------------------------------------------------------
def _utc_iso(value: datetime | None) -> str | None:
    """Stored datetimes are naive UTC; mark them so the browser shows local time."""
    return value.isoformat() + "Z" if value else None


@router.get("/status")
def status(session: Session = DB):
    settings = get_settings()
    model = get_model_instance()
    runs = list(session.scalars(select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(40)))
    counts = dict(session.execute(select(Listing.status, func.count()).group_by(Listing.status)).all())
    by_source = dict(session.execute(
        select(Listing.source, func.count()).where(Listing.status == "active").group_by(Listing.source)).all())
    from app.scheduler import scheduler_info

    return {
        "listings": counts,
        "active_by_source": by_source,
        "vehicles": session.scalar(select(func.count()).select_from(Vehicle)) or 0,
        "saved_searches": session.scalar(select(func.count()).select_from(SavedSearch)) or 0,
        "watchlist": session.scalar(select(func.count()).select_from(WatchlistItem)) or 0,
        "alerts": session.scalar(select(func.count()).select_from(AlertSent)) or 0,
        "profiles": session.scalar(select(func.count()).select_from(Profile)) or 0,
        "valuation": {"trained_at": model.trained_at if model else None, "metrics": model.metrics if model else {},
                      "rows": model.n_rows if model else 0},
        "sources": [dict(src, blocked_until=_utc_iso(blocked_until(session, src["name"]))) for src in adapters_info()],
        "settings": {
            "demo_mode": settings.demo_mode, "sources": settings.source_list, "crawl_interval_min": settings.crawl_interval_min,
            "request_delay_s": settings.crawl_request_delay_s, "ai_enabled": settings.ai_enabled,
            "claude_model": settings.claude_model, "ntfy_server": settings.ntfy_server,
            "ntfy_topic_set": bool(settings.ntfy_topic), "home_postcode": settings.home_postcode,
            "online_enrichment": settings.online_enrichment,
        },
        "scheduler": scheduler_info(),
        "crawl_runs": [
            {"id": r.id, "source": r.source, "query": r.query_key, "started_at": r.started_at, "finished_at": r.finished_at,
             "status": r.status, "fetched": r.n_fetched, "new": r.n_new, "updated": r.n_updated, "errors": r.n_errors,
             "error": r.error[:500]}
            for r in runs
        ],
    }


@router.post("/admin/crawl")
def admin_crawl(background: BackgroundTasks):
    from app.scheduler import crawl_cycle

    background.add_task(crawl_cycle)
    return {"started": True}


@router.post("/admin/retrain")
def admin_retrain(background: BackgroundTasks):
    from app.scheduler import nightly

    background.add_task(nightly)
    return {"started": True}

